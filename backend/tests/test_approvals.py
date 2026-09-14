from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from counterparty.integrations import send_ticket
from counterparty.models import AnalysisRun, ApprovalRequest, IntegrationCall, User
from counterparty.security import hash_password
from counterparty.ticket_service import create_receipt

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_exact_approval_actor_expiry_and_replay(workflow_setup, client_factory, monkeypatch):
    engine, settings, (run_id, user_id, org_id) = workflow_setup
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        run.status = "awaiting_review"
        run.report = {"model_mode": "demo"}
        session.commit()
    async with client_factory(settings) as client:
        assert (
            await client.post(
                "/api/auth/login",
                json={"email": "workflow@example.test", "password": "Test-password-2026!"},
            )
        ).status_code == 200
        proposal = await client.post(
            f"/api/runs/{run_id}/ticket-proposals",
            json={"title": "Missing evidence", "body": "Provide DPA"},
        )
        assert proposal.status_code == 201
        approval_id = proposal.json()["id"]
        assert (await client.post(f"/api/approvals/{approval_id}/execute")).status_code == 403
        assert (await client.post(f"/api/approvals/{approval_id}/approve")).status_code == 200
        assert (await client.post(f"/api/approvals/{approval_id}/approve")).status_code == 409
        with Session(engine) as session:
            from uuid import UUID

            approval = session.get(ApprovalRequest, UUID(approval_id))
            approval.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
        assert (await client.post(f"/api/approvals/{approval_id}/execute")).status_code == 409


def test_lost_response_retries_same_durable_key_without_duplicate_ticket(workflow_setup):
    from uuid import uuid4

    engine, settings, (run_id, _, org_id) = workflow_setup
    payload = {
        "organization_id": str(org_id),
        "run_id": str(run_id),
        "title": "Follow up",
        "body": "Please provide missing evidence",
    }
    call = IntegrationCall(
        organization_id=org_id,
        approval_id=uuid4(),
        idempotency_key=str(uuid4()),
        request=payload,
        attempts=0,
    )
    attempts = []

    def transport(request):
        # Real database-backed service write succeeds; only its first HTTP response is lost.
        result = create_receipt(engine, request.headers["Idempotency-Key"], payload)
        attempts.append(request.headers["Idempotency-Key"])
        if len(attempts) == 1:
            raise httpx.ReadError("Response lost", request=request)
        return httpx.Response(200, json=result)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        result = send_ticket(settings, call, client)
    assert result["run_id"] == str(run_id)
    assert call.attempts == 2
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM demo_tickets")) == 1


@pytest.mark.anyio
async def test_analyst_cannot_approve_and_other_actor_cannot_execute(
    workflow_setup, client_factory
):
    engine, settings, (run_id, _, org_id) = workflow_setup
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        run.status = "awaiting_review"
        run.report = {"model_mode": "demo"}
        user = User(
            organization_id=org_id,
            email="analyst@example.test",
            name="Analyst",
            role="analyst",
            password_hash=hash_password("Test-password-2026!"),
        )
        session.add(user)
        session.commit()
    async with client_factory(settings) as client:
        await client.post(
            "/api/auth/login",
            json={"email": "workflow@example.test", "password": "Test-password-2026!"},
        )
        proposal = (
            await client.post(
                f"/api/runs/{run_id}/ticket-proposals",
                json={"title": "Question", "body": "Please provide evidence"},
            )
        ).json()
        await client.post(f"/api/approvals/{proposal['id']}/approve")
        await client.post("/api/auth/logout")
        await client.post(
            "/api/auth/login",
            json={"email": "analyst@example.test", "password": "Test-password-2026!"},
        )
        assert (await client.post(f"/api/approvals/{proposal['id']}/approve")).status_code == 403
        assert (await client.post(f"/api/approvals/{proposal['id']}/execute")).status_code == 403


@pytest.mark.anyio
async def test_all_lost_responses_reconcile_after_expiry_without_another_write(
    workflow_setup, client_factory, monkeypatch
):
    from uuid import UUID

    from sqlalchemy import select

    from counterparty.integrations import read_receipt
    from counterparty.ticket_service import TicketReceipt, receipt_json

    engine, settings, (run_id, _, _) = workflow_setup
    writes = []

    def transport(request):
        if request.method == "POST":
            import json

            payload = json.loads(request.content)
            create_receipt(engine, request.headers["Idempotency-Key"], payload)
            writes.append(request.headers["Idempotency-Key"])
            raise httpx.ReadError("Lost response", request=request)
        key = request.url.path.rsplit("/", 1)[-1]
        with Session(engine) as session:
            row = session.scalar(select(TicketReceipt).where(TicketReceipt.idempotency_key == key))
            return httpx.Response(200, json=receipt_json(row))

    with httpx.Client(transport=httpx.MockTransport(transport)) as remote:
        monkeypatch.setattr(
            "counterparty.integrations.send_ticket",
            lambda config, call: send_ticket(config, call, remote),
        )
        monkeypatch.setattr(
            "counterparty.integrations.read_receipt",
            lambda config, call: read_receipt(config, call, remote),
        )
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            run.status = "awaiting_review"
            run.report = {"model_mode": "demo"}
            session.commit()
        async with client_factory(settings) as client:
            await client.post(
                "/api/auth/login",
                json={"email": "workflow@example.test", "password": "Test-password-2026!"},
            )
            proposal = (
                await client.post(
                    f"/api/runs/{run_id}/ticket-proposals",
                    json={"title": "Missing DPA", "body": "Please send DPA"},
                )
            ).json()
            key = proposal["id"]
            assert (await client.post(f"/api/approvals/{key}/approve")).status_code == 200
            failed = await client.post(f"/api/approvals/{key}/execute")
            assert failed.json()["status"] == "failed"
            with Session(engine) as session:
                session.get(ApprovalRequest, UUID(key)).expires_at = datetime.now(UTC) - timedelta(
                    seconds=1
                )
                session.commit()
            recovered = await client.post(f"/api/approvals/{key}/reconcile")
            assert recovered.status_code == 200, recovered.text
            assert recovered.json()["status"] == "executed"
            replay = await client.post(f"/api/approvals/{key}/execute")
            assert replay.json()["ticket"]["id"] == recovered.json()["ticket"]["id"]
    assert len(writes) == 3 and len(set(writes)) == 1
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM demo_tickets")) == 1
