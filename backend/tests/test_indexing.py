"""Durable indexing and provenance using a deterministic injected 384D test encoder."""

import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from counterparty.models import AnalysisRun, Document, DocumentChunk, User

pytestmark = pytest.mark.integration


class TestEncoder:
    __test__ = False

    def embed(self, texts, role):
        return [[1.0] + [0.0] * 383 for value in texts]


def add_evidence(engine, ids, tmp_path):
    from counterparty.documents import ingest

    run_id, user_id, _ = ids
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        doc, _ = ingest(
            session,
            session.get(User, user_id),
            b"MFA enabled",
            "proof.txt",
            "evidence",
            run.case_id,
            str(tmp_path),
        )
        session.commit()
        return doc.id


def test_upload_is_pending_and_index_publication_is_fenced(workflow_setup, tmp_path):
    from counterparty.indexing import claim_document, publish_document, request_reindex

    engine, settings, ids = workflow_setup
    doc_id = add_evidence(engine, ids, tmp_path)
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        assert doc.index_status == "pending"
        assert session.scalar(select(DocumentChunk.embedding)) is None
    claim = claim_document(engine, settings)
    assert claim is not None
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        request_reindex(session, doc)
        session.commit()
    assert publish_document(engine, claim, TestEncoder().embed(["x"], "passage")) is False
    with Session(engine) as session:
        assert session.get(Document, doc_id).index_status == "pending"
        assert session.scalar(select(DocumentChunk.embedding)) is None


def test_index_failure_atomicity_recovery_and_retry(workflow_setup, tmp_path):
    from counterparty.indexing import index_one

    engine, settings, ids = workflow_setup
    doc_id = add_evidence(engine, ids, tmp_path)

    class BrokenEncoder:
        def embed(self, texts, role):
            return [[float("nan")] * 384 for value in texts]

    assert index_one(engine, settings, BrokenEncoder())
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        assert doc.index_status == "pending"
        assert doc.index_error
        assert session.scalar(select(DocumentChunk.embedding)) is None
        doc.index_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert index_one(engine, settings, TestEncoder())
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        assert doc.index_status == "ready"
        assert doc.index_attempts == 2
        assert len(session.scalar(select(DocumentChunk.embedding))) == 384


def test_database_enforces_write_once_provenance(workflow_setup):
    from sqlalchemy.exc import DBAPIError

    engine, _, (run_id, _, _) = workflow_setup
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE analysis_runs SET retrieval_snapshot = '{}' WHERE id = :id"),
            {"id": run_id},
        )
    for column in ("input_snapshot", "retrieval_snapshot"):
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                text(f"UPDATE analysis_runs SET {column} = '{{\"changed\": true}}' WHERE id = :id"),
                {"id": run_id},
            )


def test_worker_retrieval_is_scoped_and_snapshot_reused(workflow_setup, tmp_path):
    from counterparty.documents import chunk_dict
    from counterparty.embedding_config import CONFIG, FINGERPRINT
    from counterparty.indexing import index_one, prepare_retrieval

    engine, settings, ids = workflow_setup
    run_id, _, _ = ids
    doc_id = add_evidence(engine, ids, tmp_path)
    assert index_one(engine, settings, TestEncoder())
    # New run captures evidence at enqueue time; original fixture remains immutable.
    with Session(engine) as session:
        original = session.get(AnalysisRun, run_id)
        doc = session.get(Document, doc_id)
        chunk = session.scalar(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
        snap = copy.deepcopy(original.input_snapshot)
        snap.update(
            chunks=[chunk_dict(chunk, doc)],
            requirements=[{"id": "mfa", "title": "MFA", "field": "mfa"}],
            retrieval_config=CONFIG,
            retrieval_fingerprint=FINGERPRINT,
        )
        run = AnalysisRun(
            organization_id=original.organization_id,
            case_id=original.case_id,
            created_by=original.created_by,
            policy_version_id=original.policy_version_id,
            input_snapshot=snap,
            status="running",
            lease_owner="claim",
        )
        session.add(run)
        session.commit()
        new_id = run.id
        chunk_id = str(chunk.id)
    with engine.connect() as owner:
        result = prepare_retrieval(engine, new_id, "claim", snap, TestEncoder(), owner)
    assert result["scores"] == {"mfa": {chunk_id: pytest.approx(1)}}
    with Session(engine) as session:
        run = session.get(AnalysisRun, new_id)
        assert run.input_snapshot == snap
        assert run.retrieval_snapshot == result
        doc = session.get(Document, doc_id)
        doc.index_status = "pending"
        session.commit()
    with engine.connect() as owner:
        assert prepare_retrieval(engine, new_id, "claim", snap, None, owner) == result


def test_expired_document_claim_recovers_and_exhaustion_is_visible(workflow_setup, tmp_path):
    from counterparty.indexing import claim_document, index_one, publish_document, request_reindex

    engine, settings, ids = workflow_setup
    doc_id = add_evidence(engine, ids, tmp_path)
    stale = claim_document(engine, settings)
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        doc.index_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert index_one(engine, settings, TestEncoder())
    assert not publish_document(engine, stale, TestEncoder().embed(["x"], "passage"))
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        assert doc.index_status == "ready"
        request_reindex(session, doc)
        doc.index_attempts = settings.worker_max_attempts
        session.commit()
    assert index_one(engine, settings, TestEncoder())
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        assert doc.index_status == "error"
        assert "attempt limit" in doc.index_error
        request_reindex(session, doc)
        session.commit()
    assert index_one(engine, settings, TestEncoder())


def test_model_unavailable_does_not_claim_semantic_or_block_lexical(workflow_setup):
    from counterparty.worker import process_one

    engine, settings, (run_id, _, _) = workflow_setup
    with Session(engine) as session:
        original = session.get(AnalysisRun, run_id)
        # A semantic run precedes a no-evidence run; preparation must not consume attempts.
        snap = copy.deepcopy(original.input_snapshot)
        snap["chunks"] = [
            {"id": str(uuid4()), "document_id": str(uuid4()), "kind": "evidence", "text": "proof"}
        ]
        snap["requirements"] = [{"id": "r", "title": "MFA", "field": "mfa"}]
        semantic = AnalysisRun(
            organization_id=original.organization_id,
            case_id=original.case_id,
            created_by=original.created_by,
            policy_version_id=original.policy_version_id,
            input_snapshot=snap,
            created_at=original.created_at - timedelta(seconds=10),
        )
        session.add(semantic)
        session.commit()
        semantic_id = semantic.id
    assert process_one(engine, settings, None)
    with Session(engine) as session:
        semantic = session.get(AnalysisRun, semantic_id)
        assert semantic.status == "queued" and semantic.attempts == 0
        assert session.get(AnalysisRun, run_id).status == "awaiting_review"


def test_exact_chunk_and_tenant_filters_reject_poisoned_snapshot(workflow_setup, tmp_path):
    from counterparty.documents import chunk_dict
    from counterparty.embedding_config import CONFIG, FINGERPRINT
    from counterparty.embeddings import EmbeddingError
    from counterparty.indexing import index_one, prepare_retrieval

    engine, settings, ids = workflow_setup
    doc_id = add_evidence(engine, ids, tmp_path)
    assert index_one(engine, settings, TestEncoder())
    with Session(engine) as session:
        original = session.get(AnalysisRun, ids[0])
        doc = session.get(Document, doc_id)
        chunk = session.scalar(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
        captured = chunk_dict(chunk, doc)
        # A new chunk with a matching document/config must never enter an old snapshot.
        later = DocumentChunk(
            document_id=doc_id,
            organization_id=doc.organization_id,
            case_id=doc.case_id,
            text="Later unsnapshotted evidence",
            location={},
            embedding=TestEncoder().embed(["x"], "passage")[0],
            embedding_model=FINGERPRINT,
        )
        session.add(later)
        session.flush()
        for wrong in (False, True):
            snap = copy.deepcopy(original.input_snapshot)
            snap.update(
                chunks=[captured],
                requirements=[{"id": "mfa", "title": "MFA", "field": "mfa"}],
                retrieval_config=CONFIG,
                retrieval_fingerprint=FINGERPRINT,
            )
            if wrong:
                snap["chunks"][0]["document_id"] = str(uuid4())
            run = AnalysisRun(
                organization_id=original.organization_id,
                case_id=original.case_id,
                created_by=original.created_by,
                policy_version_id=original.policy_version_id,
                input_snapshot=snap,
                status="running",
                lease_owner="claim",
            )
            session.add(run)
            session.commit()
            with engine.connect() as owner:
                if wrong:
                    with pytest.raises(EmbeddingError):
                        prepare_retrieval(engine, run.id, "claim", snap, TestEncoder(), owner)
                else:
                    result = prepare_retrieval(engine, run.id, "claim", snap, TestEncoder(), owner)
                    assert set(result["scores"]["mfa"]) == {str(chunk.id)}
                    assert str(later.id) not in result["scores"]["mfa"]
