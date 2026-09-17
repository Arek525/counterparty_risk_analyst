"""Durable document claims and write-once, exactly scoped run retrieval."""

import math
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from counterparty.embedding_config import CONFIG, FINGERPRINT, requirement_query
from counterparty.embeddings import EmbeddingError, validate_vectors
from counterparty.models import (
    AnalysisRun,
    Document,
    DocumentChunk,
    PolicySetVersion,
    WorkerModelState,
)


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


def document_chunks(session, document):
    return list(
        session.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.organization_id == document.organization_id,
                DocumentChunk.case_id == document.case_id,
            )
            .order_by(DocumentChunk.id)
        )
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
        chunks = document_chunks(session, doc)
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
        chunks = document_chunks(session, doc)
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


def narrative_queries(requirements):
    from counterparty.analysis.semantic import requirement_query as semantic_query

    return {item["id"]: semantic_query(item) for item in requirements}


def compatible_requirement_cache(cache, queries):
    return bool(
        cache
        and cache.get("fingerprint") == FINGERPRINT
        and cache.get("query_version") == "narrative-v1"
        and cache.get("queries") == queries
        and set(cache.get("vectors", {})) == set(queries)
    )


def publish_requirement_cache(policy, queries, vectors):
    policy.requirement_embeddings = {
        "fingerprint": FINGERPRINT,
        "query_version": "narrative-v1",
        "queries": queries,
        "vectors": {key: vector.tolist() for key, vector in zip(queries, vectors, strict=True)},
    }
    policy.requirement_index_status = "ready"
    policy.requirement_index_error = None


def policy_index_eligible():
    return and_(
        PolicySetVersion.status == "approved",
        PolicySetVersion.requirement_index_status == "pending",
    )


def index_policy_one(engine, model):
    """Hold one row lock through local inference; concurrent workers skip that policy."""
    if model is None:
        return False
    with Session(engine) as session:
        policy = session.scalar(
            select(PolicySetVersion)
            .where(policy_index_eligible())
            .order_by(PolicySetVersion.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if policy is None:
            return False
        try:
            queries = narrative_queries(policy.requirements)
            vectors = (
                validate_vectors(model.embed(list(queries.values()), "query"), len(queries))
                if queries
                else []
            )
            publish_requirement_cache(policy, queries, vectors)
        except Exception:
            policy.requirement_index_status = "error"
            policy.requirement_index_error = (
                "Local requirement embedding failed. Check worker model status and retry indexing."
            )
        session.commit()
    return True


def needs_embeddings(run):
    if run.input_snapshot.get(
        "assessment_version"
    ) == "semantic-v2" and compatible_requirement_cache(
        run.input_snapshot.get("requirement_embeddings"),
        narrative_queries(run.input_snapshot.get("requirements", [])),
    ):
        return False
    return (
        run.report is None
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
    semantic_v2 = snapshot.get("assessment_version") == "semantic-v2"
    queries = (
        narrative_queries(snapshot["requirements"])
        if semantic_v2
        else {req["id"]: requirement_query(req) for req in snapshot["requirements"]}
    )
    cache = snapshot.get("requirement_embeddings") if semantic_v2 else None
    if semantic_v2 and not compatible_requirement_cache(cache, queries):
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            policy = session.get(PolicySetVersion, run.policy_version_id)
            cache = policy.requirement_embeddings if policy else None
    if chunks and queries:
        if semantic_v2 and compatible_requirement_cache(cache, queries):
            vectors = [cache["vectors"][key] for key in queries]
        else:
            if model is None:
                raise EmbeddingError("Local embedding model is unavailable")
            vectors = model.embed(list(queries.values()), "query")
        vectors = validate_vectors(vectors, len(queries))
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
        result["variant"] = "hybrid"
        if semantic_v2 and queries and chunks:
            result["query_version"] = "narrative-v1"
            policy = session.scalar(
                select(PolicySetVersion)
                .where(
                    PolicySetVersion.id == run.policy_version_id,
                    PolicySetVersion.organization_id == run.organization_id,
                )
                .with_for_update()
            )
            if (
                policy
                and policy.status == "approved"
                and narrative_queries(policy.requirements) == queries
            ):
                publish_requirement_cache(policy, queries, vectors)
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
