"""Durable document claims and write-once, exactly scoped run retrieval."""

import math
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from counterparty.embedding_config import CONFIG, FINGERPRINT, requirement_query
from counterparty.embeddings import EmbeddingError, validate_vectors
from counterparty.models import AnalysisRun, Document, DocumentChunk, WorkerModelState


def request_reindex(session, document):
    if document.index_status == "pending" and document.index_config == FINGERPRINT:
        return False
    document.index_status = "pending"
    document.index_config = FINGERPRINT
    document.index_owner = None
    document.index_lease_expires_at = None
    document.index_attempts = 0
    document.index_error = None
    document.indexed_at = None
    return True


def index_eligible(now):
    return and_(
        Document.index_config == FINGERPRINT,
        Document.index_status.in_(["pending", "indexing"]),
        or_(Document.index_lease_expires_at.is_(None), Document.index_lease_expires_at < now),
    )


def claim_document(engine, settings):
    with Session(engine) as session:
        doc = session.scalar(
            select(Document)
            .where(index_eligible(datetime.now(UTC)))
            .order_by(Document.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if doc is None:
            return None
        if doc.index_attempts >= settings.worker_max_attempts:
            doc.index_status = "error"
            doc.index_error = "Indexing attempt limit exceeded. Request reindex to retry."
            doc.index_owner = None
            session.commit()
            return {"exhausted": True}
        doc.index_status = "indexing"
        doc.index_attempts += 1
        doc.index_owner = uuid4().hex
        doc.index_lease_expires_at = datetime.now(UTC) + timedelta(
            seconds=settings.worker_max_runtime_seconds + 30
        )
        chunks = list(
            session.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == doc.id,
                    DocumentChunk.organization_id == doc.organization_id,
                    DocumentChunk.case_id == doc.case_id,
                )
                .order_by(DocumentChunk.id)
            )
        )
        claim = {
            "id": doc.id,
            "owner": doc.index_owner,
            "config": doc.index_config,
            "ids": [chunk.id for chunk in chunks],
            "texts": [chunk.text for chunk in chunks],
        }
        session.commit()
        return claim


def publish_document(engine, claim, vectors):
    values = validate_vectors(vectors, len(claim["ids"]))
    with Session(engine) as session:
        doc = session.scalar(select(Document).where(Document.id == claim["id"]).with_for_update())
        if doc is None or (doc.index_status, doc.index_owner, doc.index_config) != (
            "indexing",
            claim["owner"],
            claim["config"],
        ):
            return False
        chunks = list(
            session.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == doc.id,
                    DocumentChunk.organization_id == doc.organization_id,
                    DocumentChunk.case_id == doc.case_id,
                )
                .order_by(DocumentChunk.id)
            )
        )
        if [chunk.id for chunk in chunks] != claim["ids"]:
            raise EmbeddingError("Document chunks changed during indexing")
        for chunk, vector in zip(chunks, values, strict=True):
            chunk.embedding = vector.tolist()
            chunk.embedding_model = claim["config"]
        doc.index_status = "ready"
        doc.indexed_at = datetime.now(UTC)
        doc.index_owner = None
        doc.index_lease_expires_at = None
        doc.index_error = None
        session.commit()
    return True


def index_one(engine, settings, model):
    if model is None:
        return False
    claim = claim_document(engine, settings)
    if claim is None:
        return False
    if claim.get("exhausted"):
        return True
    try:
        vectors = model.embed(claim["texts"], "passage")
        publish_document(engine, claim, vectors)
    except Exception:
        with Session(engine) as session:
            doc = session.scalar(
                select(Document).where(Document.id == claim["id"]).with_for_update()
            )
            if doc is not None and doc.index_owner == claim["owner"]:
                doc.index_status = (
                    "error" if doc.index_attempts >= settings.worker_max_attempts else "pending"
                )
                doc.index_error = (
                    "Local embedding failed. Check worker model status; reindex to retry."
                )
                doc.index_owner = None
                doc.index_lease_expires_at = datetime.now(UTC) + timedelta(
                    seconds=2**doc.index_attempts
                )
                session.commit()
    return True


def needs_embeddings(run):
    return (
        run.retrieval_variant in {"hybrid", "semantic"}
        and run.report is None
        and run.retrieval_snapshot is None
        and "retrieval_scores" not in run.input_snapshot
        and bool(run.input_snapshot.get("requirements"))
        and any(chunk.get("kind") == "evidence" for chunk in run.input_snapshot["chunks"])
    )


def prepare_retrieval(engine, run_id, claim_token, snapshot, model, owner):
    with Session(engine) as session:
        stored = session.get(AnalysisRun, run_id).retrieval_snapshot
        if stored is not None:
            return stored
    if (
        snapshot.get("retrieval_config") != CONFIG
        or snapshot.get("retrieval_fingerprint") != FINGERPRINT
    ):
        raise EmbeddingError("Run embedding configuration is incompatible. Create a new analysis.")
    chunks = [chunk for chunk in snapshot["chunks"] if chunk["kind"] == "evidence"]
    ids = {chunk["id"] for chunk in chunks}
    documents = {chunk["document_id"] for chunk in chunks}
    queries = {req["id"]: requirement_query(req) for req in snapshot["requirements"]}
    if chunks and queries:
        if model is None:
            raise EmbeddingError("Local embedding model is unavailable")
        vectors = model.embed(list(queries.values()), "query")
        validate_vectors(vectors, len(queries))
    else:
        vectors = []
    result = {
        "config": CONFIG,
        "fingerprint": FINGERPRINT,
        "queries": queries,
        "chunk_ids": sorted(ids),
        "document_ids": sorted(documents),
        "scores": {},
    }
    # The caller's checkpoint/ownership session must still be alive before publication.
    owner.execute(text("SELECT 1") if hasattr(owner, "dialect") else "SELECT 1")
    with Session(engine) as session:
        run = session.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id).with_for_update())
        if run.lease_owner != claim_token or run.status != "running":
            raise EmbeddingError("Analysis ownership changed before retrieval publication")
        if run.retrieval_snapshot is not None:
            return run.retrieval_snapshot
        # Lock the exact document rows through scoring + publication, fencing concurrent reindex.
        ready = list(
            session.scalars(
                select(Document)
                .where(
                    Document.id.in_([UUID(value) for value in documents]),
                    Document.organization_id == run.organization_id,
                    Document.case_id == run.case_id,
                    Document.kind == "evidence",
                    Document.index_status == "ready",
                    Document.index_config == FINGERPRINT,
                )
                .with_for_update()
            )
        )
        if {str(doc.id) for doc in ready} != documents:
            raise EmbeddingError(
                "Snapshotted evidence indexes are unavailable. Reindex and create a new analysis."
            )
        for index, req_id in enumerate(queries):
            if not chunks:
                result["scores"][req_id] = {}
                continue
            distance = DocumentChunk.embedding.cosine_distance(vectors[index]).label("distance")
            rows = session.execute(
                select(DocumentChunk.id, distance).where(
                    DocumentChunk.organization_id == run.organization_id,
                    DocumentChunk.case_id == run.case_id,
                    DocumentChunk.document_id.in_([UUID(value) for value in documents]),
                    DocumentChunk.id.in_([UUID(value) for value in ids]),
                    DocumentChunk.embedding_model == FINGERPRINT,
                    DocumentChunk.embedding.is_not(None),
                )
            )
            scores = {str(chunk_id): 1 - value for chunk_id, value in rows if math.isfinite(value)}
            if set(scores) != ids:
                raise EmbeddingError("Snapshotted evidence vectors are incomplete or incompatible")
            result["scores"][req_id] = scores
        # Recheck ownership immediately before committing the separately fenced business write.
        owner.execute(text("SELECT 1") if hasattr(owner, "dialect") else "SELECT 1")
        result["variant"] = run.retrieval_variant
        run.retrieval_snapshot = result
        session.commit()
    return result


def set_model_state(engine, status, error=None):
    with Session(engine) as session:
        session.merge(
            WorkerModelState(
                id="local-embeddings",
                status=status,
                config=FINGERPRINT,
                error=error,
                heartbeat_at=datetime.now(UTC),
            )
        )
        session.commit()
