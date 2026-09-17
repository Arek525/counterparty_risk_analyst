from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from counterparty.models import AnalysisRun
from counterparty.worker import process_one

pytestmark = pytest.mark.integration


@pytest.mark.anyio
@pytest.mark.parametrize("decision", ["accepted", "rejected", "needs_information"])
async def test_review_completes_without_worker(workflow_setup, client_factory, decision):
    engine, settings, (run_id, _, _) = workflow_setup
    assert process_one(engine, settings)
    with Session(engine) as session:
        before = session.get(AnalysisRun, run_id).report.copy()
    async with client_factory(settings) as client:
        await client.post(
            "/api/auth/login",
            json={"email": "workflow@example.test", "password": "Test-password-2026!"},
        )
        response = await client.post(
            f"/api/runs/{run_id}/decision",
            json={"decision": decision, "rationale": "Reviewed evidence"},
        )
        assert response.status_code == 201
        assert response.json()["report"]["workflow_complete"] is True
    assert process_one(engine, settings) is False
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "completed"
        assert run.report == {**before, "workflow_complete": True}


def test_expired_claim_is_recovered(workflow_setup):
    engine, settings, (run_id, _, _) = workflow_setup
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        run.status = "running"
        run.lease_owner = "dead-worker"
        run.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert process_one(engine, settings) is True
    with Session(engine) as session:
        assert session.get(AnalysisRun, run_id).status == "awaiting_review"


def test_advisory_lock_prevents_duplicate_execution(workflow_setup):
    from counterparty.worker import lock_key

    engine, settings, (run_id, _, _) = workflow_setup
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key(run_id)})
        connection.commit()
        try:
            assert process_one(engine, settings) is False
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key(run_id)})
            connection.commit()
    assert process_one(engine, settings) is True


def test_lost_owner_connection_cannot_overwrite_replacement_result(workflow_setup, monkeypatch):
    engine, settings, (run_id, _, _) = workflow_setup

    def lose_owner(snapshot):
        with engine.begin() as connection:
            connection.execute(
                text("""
                SELECT pg_terminate_backend(pid) FROM pg_locks
                WHERE locktype = 'advisory' AND database =
                    (SELECT oid FROM pg_database WHERE datname = current_database())
            """)
            )
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            run.lease_owner = None
            run.lease_expires_at = None
            run.status = "awaiting_review"
            run.report = {"summary": "Result from replacement worker"}
            session.commit()
        return {"summary": "Stale worker result"}

    monkeypatch.setattr("counterparty.analysis.analyze", lose_owner)
    assert process_one(engine, settings) is True
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "awaiting_review"
        assert run.report["summary"] == "Result from replacement worker"


def test_model_quota_failure_stops_job_without_outer_retry(workflow_setup, monkeypatch):
    from counterparty.analysis.adapters import ModelError

    engine, settings, (run_id, _, _) = workflow_setup
    calls = []

    def exhausted(snapshot):
        calls.append(True)
        raise ModelError("Gemini quota exhausted; stopped without fallback")

    monkeypatch.setattr("counterparty.analysis.analyze", exhausted)
    assert process_one(engine, settings)
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "failed"
        assert "quota exhausted" in run.error
        assert run.attempts == 1
    assert process_one(engine, settings) is False
    assert len(calls) == 1
