"""Sequential semantic assessment keeps successful paid steps across recovery."""

import copy

import pytest
from sqlalchemy.orm import Session

from counterparty.analysis.adapters import ModelError
from counterparty.models import AnalysisRun
from counterparty.worker import assess_sequential

pytestmark = pytest.mark.integration

POLICY_SOURCE = {
    "chunk_id": "policy-chunk",
    "document_id": "policy",
    "location": "section 1",
    "quote": "Maintain controls",
}


class Owner:
    def execute(self, query):
        return None


def semantic_run(engine, original_id):
    with Session(engine) as session:
        original = session.get(AnalysisRun, original_id)
        snapshot = copy.deepcopy(original.input_snapshot)
        snapshot.update(
            assessment_version="semantic-v2",
            requirements=[
                {
                    "id": key,
                    "title": key,
                    "description": f"Document {key} control",
                    "severity": "High",
                    "source": POLICY_SOURCE,
                }
                for key in ("first", "second", "third")
            ],
        )
        run = AnalysisRun(
            organization_id=original.organization_id,
            case_id=original.case_id,
            created_by=original.created_by,
            policy_version_id=original.policy_version_id,
            input_snapshot=snapshot,
            status="running",
            lease_owner="claim",
        )
        session.add(run)
        session.commit()
        return run.id, snapshot


def test_partial_failure_resumes_without_replaying_success(workflow_setup, monkeypatch):
    from counterparty.analysis import semantic

    engine, settings, ids = workflow_setup
    run_id, snapshot = semantic_run(engine, ids[0])
    calls = []

    def assess(requirement, chunks, relationship, **kwargs):
        key = requirement["id"]
        with Session(engine) as session:
            progress = session.get(AnalysisRun, run_id).assessment_progress
            assert progress["current_requirement_id"] == key
            assert progress["completed"] == len(set(calls) - {"second"})
        calls.append(key)
        kwargs["metrics"]["calls"] += 1
        if key == "second" and calls.count(key) == 1:
            raise ModelError("Synthetic provider failure")
        return {"requirement_id": key}

    monkeypatch.setattr(semantic, "assess_requirement", assess)
    monkeypatch.setattr(
        semantic,
        "build_report",
        lambda findings, mode, metrics: {"findings": findings, "metrics": metrics},
    )
    with pytest.raises(ModelError):
        assess_sequential(engine, settings, run_id, "claim", Owner(), snapshot)
    with Session(engine) as session:
        progress = session.get(AnalysisRun, run_id).assessment_progress
        assert progress["completed_ids"] == ["first"]
        assert progress["metrics"]["calls"] == 2

    # The provider's observer above only needs to assert the resume entry.
    def resumed(requirement, chunks, relationship, **kwargs):
        calls.append(requirement["id"])
        kwargs["metrics"]["calls"] += 1
        return {"requirement_id": requirement["id"]}

    monkeypatch.setattr(semantic, "assess_requirement", resumed)
    report = assess_sequential(engine, settings, run_id, "claim", Owner(), snapshot)
    assert calls == ["first", "second", "second", "third"]
    assert len(report["findings"]) == 3
    assert report["metrics"]["calls"] == 4


def test_lost_claim_cannot_publish_finding(workflow_setup, monkeypatch):
    from counterparty.analysis import semantic
    from counterparty.embeddings import EmbeddingError

    engine, settings, ids = workflow_setup
    run_id, snapshot = semantic_run(engine, ids[0])

    def assess(*args, **kwargs):
        with Session(engine) as session:
            session.get(AnalysisRun, run_id).lease_owner = "new-owner"
            session.commit()
        return {"requirement_id": "first"}

    monkeypatch.setattr(semantic, "assess_requirement", assess)
    with pytest.raises(EmbeddingError, match="ownership changed"):
        assess_sequential(engine, settings, run_id, "claim", Owner(), snapshot)
    with Session(engine) as session:
        progress = session.get(AnalysisRun, run_id).assessment_progress
        assert progress["findings"] == []
        assert progress["attempts"] == {"first": 1}


def test_requirement_attempt_bound_survives_retries(workflow_setup, monkeypatch):
    from counterparty.analysis import semantic

    engine, settings, ids = workflow_setup
    run_id, snapshot = semantic_run(engine, ids[0])
    calls = []

    def assess(*args, **kwargs):
        calls.append(1)
        raise ModelError("Synthetic failure")

    monkeypatch.setattr(semantic, "assess_requirement", assess)
    for _ in range(4):
        with pytest.raises(ModelError):
            assess_sequential(engine, settings, run_id, "claim", Owner(), snapshot)
    assert len(calls) == 3


def test_approved_requirement_cache_reused_for_retrieval(workflow_setup, tmp_path):
    from sqlalchemy import select
    from test_indexing import TestEncoder, add_evidence

    from counterparty.documents import chunk_dict
    from counterparty.embedding_config import CONFIG, FINGERPRINT
    from counterparty.indexing import index_one, index_policy_one, prepare_retrieval
    from counterparty.models import Document, DocumentChunk, PolicySetVersion

    engine, settings, ids = workflow_setup
    doc_id = add_evidence(engine, ids, tmp_path)
    index_one(engine, settings, TestEncoder())
    requirements = [
        {
            "id": "control",
            "title": "General control",
            "description": "Maintain a written deletion schedule",
            "severity": "High",
            "source": POLICY_SOURCE,
            "applicability_text": "Applies when personal data is processed",
        }
    ]
    with Session(engine) as session:
        original = session.get(AnalysisRun, ids[0])
        policy = session.get(PolicySetVersion, original.policy_version_id)
        # Approved fixture cannot be edited; create a separate approved version.
        policy = PolicySetVersion(
            organization_id=original.organization_id,
            created_by=original.created_by,
            name="Narrative",
            version=1,
            status="approved",
            document_ids=[],
            requirements=requirements,
        )
        session.add(policy)
        session.commit()
        policy_id = policy.id
    # Empty original policy is indexed first, then the new narrative policy.
    while index_policy_one(engine, TestEncoder()):
        pass
    with Session(engine) as session:
        original = session.get(AnalysisRun, ids[0])
        policy = session.get(PolicySetVersion, policy_id)
        cache = policy.requirement_embeddings
        assert "written deletion schedule" in cache["queries"]["control"]
        assert "personal data" in cache["queries"]["control"]
        document = session.get(Document, doc_id)
        chunk = session.scalar(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
        snapshot = {
            **original.input_snapshot,
            "assessment_version": "semantic-v2",
            "requirements": requirements,
            "chunks": [chunk_dict(chunk, document)],
            "retrieval_config": CONFIG,
            "retrieval_fingerprint": FINGERPRINT,
            "requirement_embeddings": cache,
        }
        run = AnalysisRun(
            organization_id=original.organization_id,
            case_id=original.case_id,
            created_by=original.created_by,
            policy_version_id=policy_id,
            input_snapshot=snapshot,
            status="running",
            lease_owner="claim",
        )
        session.add(run)
        session.commit()
        run_id = run.id
    # No encoder is available: successful scoring proves reuse of cached vectors.
    with engine.connect() as owner:
        retrieval = prepare_retrieval(engine, run_id, "claim", snapshot, None, owner)
    assert retrieval["query_version"] == "narrative-v1"
    assert len(retrieval["scores"]["control"]) == 1


def test_semantic_run_reaches_durable_review_without_legacy_analysis(workflow_setup, monkeypatch):
    import counterparty.analysis
    from counterparty.worker import process_one

    engine, settings, ids = workflow_setup
    run_id, _ = semantic_run(engine, ids[0])
    with Session(engine) as session:
        session.get(AnalysisRun, ids[0]).status = "failed"
        run = session.get(AnalysisRun, run_id)
        run.status = "queued"
        run.lease_owner = None
        session.commit()

    def legacy(*args):
        raise AssertionError("New snapshots must not use the legacy analyzer")

    monkeypatch.setattr(counterparty.analysis, "analyze", legacy)
    assert process_one(engine, settings)
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "awaiting_review"
        assert run.assessment_progress["completed"] == 3
        assert len(run.report["findings"]) == 3
        assert run.report["metrics"]["calls"] == 0


def test_model_change_stops_before_consuming_requirement_attempt(workflow_setup, monkeypatch):
    from counterparty.analysis import semantic

    engine, settings, ids = workflow_setup
    run_id, snapshot = semantic_run(engine, ids[0])
    snapshot.update(
        model_mode="gemini",
        model_name="gemini-original",
        chunks=[{"kind": "evidence", "text": "Written control"}],
    )
    monkeypatch.setenv("GEMINI_MODEL", "gemini-replacement")

    def forbidden(*args, **kwargs):
        raise AssertionError("Changed model must not be invoked")

    monkeypatch.setattr(semantic, "assess_requirement", forbidden)
    with pytest.raises(ModelError, match="differs from this analysis snapshot"):
        assess_sequential(engine, settings, run_id, "claim", Owner(), snapshot)
    with Session(engine) as session:
        assert session.get(AnalysisRun, run_id).assessment_progress is None


def test_progress_waits_for_concurrent_checkpoint_write(workflow_setup, monkeypatch):
    import time
    from contextlib import contextmanager
    from threading import Event

    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver

    from counterparty.worker import process_one

    engine, settings, ids = workflow_setup
    run_id, _ = semantic_run(engine, ids[0])
    with Session(engine) as session:
        session.get(AnalysisRun, ids[0]).status = "failed"
        run = session.get(AnalysisRun, run_id)
        run.status = "queued"
        run.lease_owner = None
        session.commit()

    writing = Event()
    overlapped = []
    cursor = PostgresSaver._cursor
    execute = psycopg.Connection.execute

    @contextmanager
    def slow_checkpoint(self, *, pipeline=False):
        with cursor(self, pipeline=pipeline) as current:
            if pipeline:
                writing.set()
                time.sleep(0.1)
            try:
                yield current
            finally:
                if pipeline:
                    writing.clear()

    def guarded_execute(self, query, *args, **kwargs):
        if query == "SELECT 1" and writing.is_set():
            overlapped.append(True)
            raise psycopg.OperationalError("Concurrent checkpoint pipeline")
        return execute(self, query, *args, **kwargs)

    monkeypatch.setattr(PostgresSaver, "_cursor", slow_checkpoint)
    monkeypatch.setattr(psycopg.Connection, "execute", guarded_execute)
    assert process_one(engine, settings)
    assert not overlapped
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run.status == "awaiting_review"
        assert run.assessment_progress["completed"] == 3
