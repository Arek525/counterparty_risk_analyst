"""Deletion contracts against disposable PostgreSQL, including worker locks."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from counterparty.models import (
    AnalysisRun,
    AssessmentCase,
    AuditEvent,
    Decision,
    Document,
    DocumentChunk,
    PolicySetVersion,
    User,
)
from counterparty.worker import lock_key, process_one

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def login(client):
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "workflow@example.test",
            "password": "Test-password-2026!",
        },
    )
    assert response.status_code == 200


async def test_delete_case_purges_content_files_and_dependents(workflow_setup, client_factory):
    engine, settings, (run_id, user_id, org_id) = workflow_setup
    assert process_one(engine, settings)
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        case_id, policy_id = run.case_id, run.policy_version_id
        session.add(
            Decision(
                organization_id=org_id,
                run_id=run_id,
                actor_id=user_id,
                decision="needs_information",
                rationale="Private decision",
            )
        )
        run.status = "completed"
        session.commit()
    async with client_factory(settings) as client:
        await login(client)
        uploaded = await client.post(
            "/api/documents",
            data={"kind": "evidence", "case_id": str(case_id)},
            files={"file": ("evidence.txt", b"Private counterparty document.")},
        )
        assert uploaded.status_code == 201, uploaded.text
        with Session(engine) as session:
            doc = session.scalar(select(Document).where(Document.case_id == case_id))
            path = Path(settings.storage_path) / doc.storage_key
            assert path.exists()
        assert (await client.delete(f"/api/policies/{policy_id}")).status_code == 409
        response = await client.delete(f"/api/cases/{case_id}")
        assert response.status_code == 200, response.text
        assert not path.exists()
        assert (await client.get(f"/api/runs/{run_id}")).status_code == 404
        assert (await client.delete(f"/api/policies/{policy_id}")).status_code == 200
    with Session(engine) as session:
        for model in (
            AnalysisRun,
            Decision,
            AssessmentCase,
            Document,
            DocumentChunk,
            PolicySetVersion,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        events = session.scalars(select(AuditEvent).where(AuditEvent.event != "auth.login")).all()
        assert {event.event for event in events} <= {"case.deleted", "policy.deleted"}
        assert all(set(event.details) == {"resource_id"} for event in events)


async def test_deletion_guards_worker_row_and_reference_locks(workflow_setup, client_factory):
    engine, settings, (run_id, _, org_id) = workflow_setup
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        case_id, policy_id = run.case_id, run.policy_version_id
    async with client_factory(settings) as client:
        await login(client)
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key(run_id)})
            connection.commit()
            try:
                assert (await client.delete(f"/api/runs/{run_id}")).status_code == 409
                assert (await client.delete(f"/api/cases/{case_id}")).status_code == 409
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key(run_id)}
                )
                connection.commit()
        with Session(engine) as other:
            other.scalar(
                select(PolicySetVersion).where(PolicySetVersion.id == policy_id).with_for_update()
            )
            assert (await client.delete(f"/api/policies/{policy_id}")).status_code == 409
        with Session(engine) as other:
            other.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                {"scope": f"references:{org_id}"},
            )
            assert (await client.delete(f"/api/runs/{run_id}")).status_code == 409
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            run.status = "running"
            session.commit()
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 409
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            run.status = "queued"
            session.commit()
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 200
        assert (await client.get(f"/api/cases/{case_id}")).status_code == 200
        assert (await client.get(f"/api/policies/{policy_id}")).status_code == 200


async def test_analyst_cannot_delete_reviewed_information_request(workflow_setup, client_factory):
    engine, settings, (run_id, user_id, org_id) = workflow_setup
    with Session(engine) as session:
        session.add(
            Decision(
                organization_id=org_id,
                run_id=run_id,
                actor_id=user_id,
                decision="needs_information",
                rationale="Add current evidence and run another assessment.",
            )
        )
        session.get(User, user_id).role = "analyst"
        session.commit()
    async with client_factory(settings) as client:
        await login(client)
        response = await client.delete(f"/api/runs/{run_id}")
        assert response.status_code == 403
        assert (await client.get(f"/api/runs/{run_id}")).status_code == 200
        with Session(engine) as session:
            session.get(User, user_id).role = "reviewer"
            session.commit()
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 200


async def test_document_references_indexing_and_policy_extraction_guards(
    workflow_setup, client_factory
):
    engine, settings, (run_id, _, _) = workflow_setup
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        policy_id = run.policy_version_id
    async with client_factory(settings) as client:
        await login(client)
        uploaded = await client.post(
            "/api/documents",
            data={"kind": "policy"},
            files={"file": ("policy.txt", b"Policy source text.")},
        )
        assert uploaded.status_code == 201
        doc_id = uploaded.json()["id"]
        with Session(engine) as session:
            policy = session.get(PolicySetVersion, policy_id)
            policy.document_ids = [doc_id]
            policy.extraction_status = "extracting"
            session.commit()
        assert (await client.delete(f"/api/policies/{policy_id}")).status_code == 409
        response = await client.delete(f"/api/documents/{doc_id}")
        assert response.status_code == 409
        assert "policy versions" in response.json()["detail"]
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 200
        with Session(engine) as session:
            session.get(PolicySetVersion, policy_id).extraction_status = "ready"
            session.commit()
        assert (await client.delete(f"/api/policies/{policy_id}")).status_code == 200
        with Session(engine) as session:
            doc = session.scalar(select(Document))
            doc.index_status = "indexing"
            doc.index_lease_expires_at = datetime.now(UTC) + timedelta(seconds=120)
            session.commit()
        assert (await client.delete(f"/api/documents/{doc_id}")).status_code == 409
        with Session(engine) as session:
            doc = session.scalar(select(Document))
            doc.index_status = "error"
            session.commit()
        assert (await client.delete(f"/api/documents/{doc_id}")).status_code == 200


async def test_deletion_respects_reviewer_only_cases_and_shared_reports(
    workflow_setup, client_factory
):
    from counterparty.organizations import Organization

    engine, settings, (run_id, user_id, _) = workflow_setup
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        case_id, policy_id = run.case_id, run.policy_version_id
        actor = session.get(User, user_id)
        peer = User(
            organization_id=actor.organization_id,
            email="peer@test.example",
            name="Peer",
            password_hash=actor.password_hash,
            role="analyst",
        )
        session.add(peer)
        session.flush()
        session.get(AssessmentCase, case_id).owner_id = peer.id
        actor.role = "analyst"
        session.commit()
    async with client_factory(settings) as client:
        await login(client)
        assert (await client.delete(f"/api/cases/{case_id}")).status_code == 403
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 200
        with Session(engine) as session:
            foreign = Organization(slug="foreign-deletion", name="Other", is_synthetic=True)
            session.add(foreign)
            session.flush()
            actor = session.get(User, user_id)
            actor.organization_id = foreign.id
            actor.role = "reviewer"
            session.commit()
        assert (await client.delete(f"/api/cases/{case_id}")).status_code == 404
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 404
        assert (await client.delete(f"/api/policies/{policy_id}")).status_code == 404


async def test_bootstrap_does_not_restore_deleted_seed(workflow_setup, client_factory):
    from counterparty.bootstrap import DEMO_PASSWORD, bootstrap

    engine, settings, _ = workflow_setup
    fixtures = Path("/datasets/synthetic")
    first = bootstrap(engine, settings, fixtures)
    assert first["policies"] == 1
    async with client_factory(settings) as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "reviewer@northstar.demo",
                "password": DEMO_PASSWORD,
            },
        )
        assert response.status_code == 200
        case = (await client.get("/api/cases")).json()[0]
        assert (await client.delete(f"/api/cases/{case['id']}")).status_code == 200
        policy = (await client.get("/api/policies")).json()[0]
        assert (await client.delete(f"/api/policies/{policy['id']}")).status_code == 200
        for doc_id in policy["document_ids"]:
            assert (await client.delete(f"/api/documents/{doc_id}")).status_code == 200
        assert bootstrap(engine, settings, fixtures) == {
            "users": 0,
            "policies": 0,
            "cases": 0,
            "documents": 0,
        }
        assert (await client.get("/api/policies")).json() == []
        assert (await client.get("/api/documents")).json() == []


async def test_file_cleanup_retries_after_io_failure(workflow_setup, client_factory, monkeypatch):
    from counterparty.deletion import cleanup_files

    engine, settings, _ = workflow_setup
    async with client_factory(settings) as client:
        await login(client)
        uploaded = await client.post(
            "/api/documents",
            data={"kind": "policy"},
            files={"file": ("cleanup.txt", b"Deleted file content.")},
        )
        document_id = uploaded.json()["id"]
        with Session(engine) as session:
            doc = session.scalar(select(Document))
            path = Path(settings.storage_path) / doc.storage_key
        original_unlink = Path.unlink

        def fail_unlink(self, **kwargs):
            raise PermissionError("Simulated filesystem failure")

        monkeypatch.setattr(Path, "unlink", fail_unlink)
        response = await client.delete(f"/api/documents/{document_id}")
        assert response.status_code == 200
        assert response.json()["cleanup_pending"] is True
        assert path.exists()
        with Session(engine) as session:
            assert session.scalar(select(Document)) is None
            assert session.scalar(
                select(AuditEvent).where(AuditEvent.event == "storage.cleanup_pending")
            )
        monkeypatch.setattr(Path, "unlink", original_unlink)
        assert cleanup_files(engine, settings.storage_path) == set()
        assert not path.exists()
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(AuditEvent).where(AuditEvent.event == "storage.cleanup_pending")
                )
                is None
            )


async def test_abandoned_extraction_and_indexing_can_be_deleted(workflow_setup, client_factory):
    engine, settings, (run_id, _, _) = workflow_setup
    with Session(engine) as session:
        policy_id = session.get(AnalysisRun, run_id).policy_version_id
        policy = session.get(PolicySetVersion, policy_id)
        policy.extraction_status = "extracting"
        policy.created_at = datetime.now(UTC) - timedelta(minutes=10)
        session.commit()
    async with client_factory(settings) as client:
        await login(client)
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 200
        assert (await client.delete(f"/api/policies/{policy_id}")).status_code == 200
        uploaded = await client.post(
            "/api/documents",
            data={"kind": "policy"},
            files={"file": ("stale.txt", b"Abandoned indexing.")},
        )
        document_id = uploaded.json()["id"]
        with Session(engine) as session:
            doc = session.scalar(select(Document))
            doc.index_status = "indexing"
            doc.index_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
        assert (await client.delete(f"/api/documents/{document_id}")).status_code == 200
