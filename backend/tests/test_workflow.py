from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from counterparty.models import AnalysisRun, Decision
from counterparty.worker import process_one

pytestmark = pytest.mark.integration


def test_workflow_persists_pause_and_resumes_decision(workflow_setup):
    engine, settings, (run_id, user_id, org_id) = workflow_setup
    assert process_one(engine, settings) is True
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "awaiting_review"
        assert run.report["model_mode"] == "demo"
        assert session.scalar(text("SELECT count(*) FROM checkpoints")) > 0
        session.add(
            Decision(
                organization_id=org_id,
                run_id=run_id,
                actor_id=user_id,
                decision="needs_information",
                rationale="Missing evidence",
            )
        )
        run.status = "completed"
        session.commit()
    # New process invocation reloads checkpoints; it does not need Python memory.
    assert process_one(engine, settings) is True
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "completed"
        assert run.report["workflow_complete"] is True
    assert process_one(engine, settings) is False


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

    def lose_owner(snapshot, variant):
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


def test_finalization_failure_preserves_completed_human_decision(workflow_setup, monkeypatch):
    engine, settings, (run_id, user_id, org_id) = workflow_setup
    assert process_one(engine, settings)
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        run.attempts = settings.worker_max_attempts + 2
        run.status = "completed"
        session.add(
            Decision(
                organization_id=org_id,
                run_id=run_id,
                actor_id=user_id,
                decision="rejected",
                rationale="Insufficient evidence",
            )
        )
        session.commit()

    def broken_graph(saver):
        raise RuntimeError("Checkpoint unavailable")

    monkeypatch.setattr("counterparty.worker.build_graph", broken_graph)
    assert process_one(engine, settings)
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "completed"
        assert run.report["workflow_complete"] is False
        assert run.report["workflow_error"]
    assert process_one(engine, settings) is False


def test_finalization_preserves_reviewed_report_when_checkpoint_report_differs(workflow_setup):
    import copy

    from counterparty.worker import build_graph, checkpointer

    engine, settings, (run_id, user_id, org_id) = workflow_setup
    assert process_one(engine, settings)
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "awaiting_review"
        reviewed_report = copy.deepcopy(run.report)

    # Simulate an older executor's different checkpoint after the business report
    # was presented for review. A human decision must never authorize that report.
    with checkpointer(engine) as saver:
        graph = build_graph(saver)
        config = {"configurable": {"thread_id": str(run_id)}, "recursion_limit": 8}
        graph.update_state(
            config,
            {"report": {"summary": "Unreviewed checkpoint report", "risk": "Low"}},
            as_node="assess",
        )
        graph.invoke(None, config)
        assert graph.get_state(config).values["report"]["summary"] == "Unreviewed checkpoint report"

    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        session.add(
            Decision(
                organization_id=org_id,
                run_id=run_id,
                actor_id=user_id,
                decision="needs_information",
                rationale="Decision binds to the report actually reviewed",
            )
        )
        run.status = "completed"
        session.commit()

    assert process_one(engine, settings)
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "completed"
        assert run.report == {**reviewed_report, "workflow_complete": True}
    assert process_one(engine, settings) is False
