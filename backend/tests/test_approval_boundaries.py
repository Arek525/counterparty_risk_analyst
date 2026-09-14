"""Exact actor, version, argument and concurrency boundaries on real PostgreSQL."""

import copy
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from counterparty.integrations import Proposal as TicketProposal
from counterparty.integrations import approve, execute, propose
from counterparty.models import (
    AnalysisRun,
    ApprovalRequest,
    IntegrationCall,
    PolicySetVersion,
    User,
)
from counterparty.routes import chunks_for, create_run, reference_lock
from counterparty.schemas import RunCreate
from counterparty.security import hash_password
from counterparty.ticket_service import create_receipt

pytestmark = pytest.mark.integration
PASSWORD = "Test-password-2026!"


def ready_report(engine, run_id):
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        run.report = {"model_mode": "demo"}
        run.status = "awaiting_review"
        session.commit()


async def login(client, email="workflow@example.test"):
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text


async def approved_proposal(client, run_id):
    response = await client.post(
        f"/api/runs/{run_id}/ticket-proposals",
        json={"title": "Missing DPA", "body": "Please provide a signed agreement."},
    )
    assert response.status_code == 201, response.text
    approval_id = response.json()["id"]
    assert (await client.post(f"/api/approvals/{approval_id}/approve")).status_code == 200
    return UUID(approval_id)


@pytest.mark.anyio
async def test_second_reviewer_cannot_execute_first_reviewers_approval(
    workflow_setup, client_factory, monkeypatch
):
    engine, settings, (run_id, user_id, org_id) = workflow_setup
    ready_report(engine, run_id)
    with Session(engine) as session:
        session.add(
            User(
                organization_id=org_id,
                email="second-reviewer@example.test",
                name="Second reviewer",
                role="reviewer",
                password_hash=hash_password(PASSWORD),
            )
        )
        session.commit()
    outbound = []

    def unexpected_write(*args):
        outbound.append(args)
        pytest.fail("An action approved by another reviewer must never reach the external service")

    monkeypatch.setattr("counterparty.integrations.send_ticket", unexpected_write)
    async with client_factory(settings) as client:
        await login(client)
        approval_id = await approved_proposal(client, run_id)
        await login(client, "second-reviewer@example.test")
        denied = await client.post(f"/api/approvals/{approval_id}/execute")
        assert denied.status_code == 403
        assert "actor who approved" in denied.json()["detail"]
    assert outbound == []
    with Session(engine) as session:
        approval = session.get(ApprovalRequest, approval_id)
        call = session.scalar(
            select(IntegrationCall).where(IntegrationCall.approval_id == approval_id)
        )
        assert approval.approved_by == user_id and approval.status == "approved"
        assert call.status == "pending" and call.attempts == 0


@pytest.mark.anyio
async def test_superseded_run_invalidates_previously_approved_action(
    workflow_setup, client_factory, monkeypatch
):
    engine, settings, (run_id, user_id, org_id) = workflow_setup
    ready_report(engine, run_id)
    monkeypatch.setattr(
        "counterparty.integrations.send_ticket",
        lambda *args: pytest.fail("Superseded approval reached external service"),
    )
    async with client_factory(settings) as client:
        await login(client)
        approval_id = await approved_proposal(client, run_id)
        with Session(engine) as session:
            previous = session.get(AnalysisRun, run_id)
            session.add(
                AnalysisRun(
                    organization_id=org_id,
                    case_id=previous.case_id,
                    created_by=user_id,
                    policy_version_id=previous.policy_version_id,
                    input_snapshot=copy.deepcopy(previous.input_snapshot),
                    status="queued",
                    created_at=datetime.now(UTC) + timedelta(seconds=1),
                )
            )
            session.commit()
        denied = await client.post(f"/api/approvals/{approval_id}/execute")
        assert denied.status_code == 409
        assert "superseded" in denied.json()["detail"]
        assert (
            await client.post(
                f"/api/runs/{run_id}/ticket-proposals",
                json={"title": "Stale follow up", "body": "Wrong version"},
            )
        ).status_code == 409
    with Session(engine) as session:
        call = session.scalar(
            select(IntegrationCall).where(IntegrationCall.approval_id == approval_id)
        )
        assert call.status == "pending" and call.attempts == 0


@pytest.mark.anyio
@pytest.mark.parametrize("mutation", ["approval_arguments", "persisted_request"])
async def test_argument_tampering_is_rejected_before_outbound_write(
    workflow_setup, client_factory, monkeypatch, mutation
):
    engine, settings, (run_id, _, _) = workflow_setup
    ready_report(engine, run_id)
    monkeypatch.setattr(
        "counterparty.integrations.send_ticket",
        lambda *args: pytest.fail("Modified approved arguments reached external service"),
    )
    async with client_factory(settings) as client:
        await login(client)
        approval_id = await approved_proposal(client, run_id)
        with Session(engine) as session:
            if mutation == "approval_arguments":
                approval = session.get(ApprovalRequest, approval_id)
                approval.arguments = {**approval.arguments, "body": "Changed after human approval"}
            else:
                call = session.scalar(
                    select(IntegrationCall).where(IntegrationCall.approval_id == approval_id)
                )
                call.request = {**call.request, "title": "Changed persisted write"}
            session.commit()
        denied = await client.post(f"/api/approvals/{approval_id}/execute")
        assert denied.status_code == 409
        assert "arguments" in denied.json()["detail"]
    with Session(engine) as session:
        assert session.get(ApprovalRequest, approval_id).status == "approved"
        assert (
            session.scalar(
                select(IntegrationCall.attempts).where(IntegrationCall.approval_id == approval_id)
            )
            == 0
        )


def test_new_run_waits_until_authorized_outbound_write_commits(
    workflow_setup, monkeypatch, tmp_path
):
    """Events pause the write; PostgreSQL lock state proves creation is actually blocked."""
    from counterparty.analysis import propose_requirements
    from counterparty.documents import ingest

    engine, settings, (run_id, user_id, _) = workflow_setup
    settings.storage_path = str(tmp_path)
    ready_report(engine, run_id)
    with Session(engine) as session:
        user = session.get(User, user_id)
        original_run = session.get(AnalysisRun, run_id)
        case_id, policy_id = original_run.case_id, original_run.policy_version_id
        policy = session.get(PolicySetVersion, policy_id)
        document, _ = ingest(
            session,
            user,
            b"Hosting region must be EU.",
            "policy.md",
            "policy",
            None,
            settings.storage_path,
        )
        policy.document_ids = [str(document.id)]
        policy.requirements = propose_requirements(chunks_for(session, [document]))
        session.commit()
        proposal = propose(
            run_id, TicketProposal(title="Question", body="Please send evidence"), session, user
        )
        approval_id = UUID(proposal["id"])
        approve(approval_id, session, user)

    outbound_started = Event()
    release_outbound = Event()
    creation_attempted_lock = Event()
    creation_acquired_lock = Event()
    waiting_backend = []
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))

    def paused_write(config, call):
        outbound_started.set()
        assert release_outbound.wait(5), "Test did not release the external write"
        call.attempts += 1
        return create_receipt(engine, call.idempotency_key, call.request)

    def observed_reference_lock(session, user):
        waiting_backend.append(session.connection().connection.driver_connection.info.backend_pid)
        creation_attempted_lock.set()
        reference_lock(session, user)
        creation_acquired_lock.set()

    monkeypatch.setattr("counterparty.integrations.send_ticket", paused_write)
    # Integrations retains the real lock; observe only the create_run call's lock.
    monkeypatch.setattr("counterparty.routes.reference_lock", observed_reference_lock)

    def execute_action():
        with Session(engine) as session:
            return execute(approval_id, request, session, session.get(User, user_id))

    def create_next_run():
        with Session(engine) as session:
            return create_run(
                case_id,
                RunCreate(policy_version_id=policy_id),
                request,
                session.get(User, user_id),
                session,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        sending = executor.submit(execute_action)
        assert outbound_started.wait(3), "External write did not start"
        creating = executor.submit(create_next_run)
        try:
            assert creation_attempted_lock.wait(1), "Run creation did not request its shared lock"
            deadline = time.monotonic() + 1
            blockers = []
            with engine.connect() as observer:
                # Condition-based observation, no fixed sleep or assumed scheduling delay.
                while time.monotonic() < deadline:
                    blockers = observer.scalar(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": waiting_backend[0]}
                    )
                    if blockers:
                        break
            assert blockers, "PostgreSQL did not block run creation behind the outbound write"
            assert not creation_acquired_lock.is_set()
        finally:
            release_outbound.set()
        sent = sending.result(timeout=5)
        created = creating.result(timeout=5)
    assert sent["status"] == "executed"
    assert creation_acquired_lock.is_set()
    assert created["id"] != run_id
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 2
        assert session.scalar(text("SELECT count(*) FROM demo_tickets")) == 1
