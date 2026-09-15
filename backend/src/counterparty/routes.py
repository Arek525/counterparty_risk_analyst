"""Organization/case scoped API for document preparation and immutable assessments."""

import copy
import math
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.orm import Session

from counterparty.documents import chunk_dict, ingest, read_upload
from counterparty.models import (
    AnalysisRun,
    AssessmentCase,
    AuditEvent,
    AuthSession,
    Decision,
    Document,
    DocumentChunk,
    PolicySetVersion,
    User,
)
from counterparty.schemas import (
    CaseCreate,
    CasePatch,
    DecisionCreate,
    Login,
    PolicyProposal,
    Requirement,
    RequirementEdit,
    RunCreate,
)
from counterparty.security import (
    COOKIE_NAME,
    REVIEW_ROLES,
    WRITE_ROLES,
    audit,
    check_origin,
    current_user,
    get_case,
    get_session,
    require_roles,
    token_hash,
    verify_password,
)

router = APIRouter(prefix="/api")
DB = Annotated[Session, Depends(get_session)]
Actor = Annotated[User, Depends(current_user)]


def public_user(user):
    return {key: getattr(user, key) for key in ("id", "organization_id", "email", "role", "name")}


def public_case(case):
    return {
        key: getattr(case, key)
        for key in (
            "id",
            "organization_id",
            "owner_id",
            "name",
            "counterparty_name",
            "relationship",
            "created_at",
            "updated_at",
        )
    }


def public_document(document):
    return {
        key: getattr(document, key)
        for key in (
            "id",
            "case_id",
            "kind",
            "filename",
            "sha256",
            "version",
            "media_type",
            "evidence_type",
            "created_at",
        )
    }


def public_policy(policy):
    return {
        key: getattr(policy, key)
        for key in (
            "id",
            "name",
            "version",
            "status",
            "document_ids",
            "requirements",
            "created_by",
            "approved_by",
            "created_at",
            "approved_at",
        )
    }


def policy_for(session, user, policy_id, lock=False):
    query = select(PolicySetVersion).where(
        PolicySetVersion.id == policy_id, PolicySetVersion.organization_id == user.organization_id
    )
    policy = session.scalar(query.with_for_update() if lock else query)
    if policy is None:
        raise HTTPException(404, "Policy version not found")
    return policy


def document_for(session, user, document_id):
    document = session.scalar(
        select(Document).where(
            Document.id == document_id, Document.organization_id == user.organization_id
        )
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    if document.case_id:
        get_case(session, user, document.case_id)
    return document


def run_for(session, user, run_id, lock=False):
    query = select(AnalysisRun).where(
        AnalysisRun.id == run_id, AnalysisRun.organization_id == user.organization_id
    )
    run = session.scalar(query.with_for_update() if lock else query)
    if run is None:
        raise HTTPException(404, "Run not found")
    get_case(session, user, run.case_id)
    return run


def chunks_for(session, documents):
    result = []
    for document in documents:
        chunks = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.id)
        ).all()
        # Source order is stable even though chunk UUIDs are random.
        chunks = sorted(
            chunks, key=lambda c: (c.location.get("page", 0), c.location.get("line_start", 0))
        )
        result.extend(chunk_dict(chunk, document) for chunk in chunks)
    return result


def validated_requirements(requirements, chunks):
    from counterparty.analysis import validate_requirements

    try:
        parsed = [Requirement.model_validate(item).model_dump(mode="json") for item in requirements]
        if not parsed or len(parsed) > 100:
            raise ValueError("A policy needs between 1 and 100 requirements")
        if len({item["id"] for item in parsed}) != len(parsed):
            raise ValueError("Requirement identifiers must be unique")
        sources = {chunk["id"]: chunk for chunk in chunks}
        for item in parsed:
            source = item["source"]
            chunk = sources.get(source["chunk_id"])
            if (
                chunk is None
                or source["document_id"] != chunk["document_id"]
                or source["location"] != chunk["location"]
                or source["quote"] not in chunk["text"]
            ):
                raise ValueError("Requirement citation does not resolve to the policy source")
        validate_requirements(parsed, chunks)
        return parsed
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, "Invalid requirement schema or unresolved policy source") from exc


def policy_documents(session, user, policy):
    documents = [document_for(session, user, UUID(value)) for value in policy.document_ids]
    if any(document.kind != "policy" or document.case_id is not None for document in documents):
        raise HTTPException(422, "Policy must reference organization policy documents")
    return documents


@router.get("/meta")
def meta(request: Request):
    settings = request.app.state.settings
    return {
        "version": "0.2.0",
        "demo_mode": settings.demo_mode,
        "model_mode": settings.model_mode,
        "max_upload_bytes": 10 * 1024 * 1024,
    }


@router.get("/demo/accounts")
def demo_accounts(request: Request):
    if not request.app.state.settings.demo_mode:
        raise HTTPException(404, "Demo mode disabled")
    from counterparty.bootstrap import DEMO_ACCOUNTS, DEMO_PASSWORD

    return [{**account, "password": DEMO_PASSWORD} for account in DEMO_ACCOUNTS]


@router.post("/auth/login")
def login(body: Login, request: Request, response: Response, session: DB):
    check_origin(request)
    user = session.scalar(select(User).where(User.email == body.email.lower()))
    # Always run a password KDF so nonexistent emails do not take a fast path.
    encoded = (
        user.password_hash
        if user
        else ("pbkdf2_sha256$600000$00000000000000000000000000000000$" + "0" * 64)
    )
    valid = verify_password(body.password, encoded)
    if user is None or not user.is_active or not valid:
        raise HTTPException(401, "Invalid credentials")
    if not request.app.state.settings.demo_mode:
        from counterparty.bootstrap import DEMO_ACCOUNTS

        if user.email in {account["email"] for account in DEMO_ACCOUNTS}:
            raise HTTPException(403, "Demo accounts are disabled")
    token = secrets.token_urlsafe(32)
    old = request.cookies.get(COOKIE_NAME)
    if old:
        session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(old)))
    session.execute(delete(AuthSession).where(AuthSession.expires_at <= datetime.now(UTC)))
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=datetime.now(UTC) + timedelta(hours=12),
        )
    )
    audit(session, user, "auth.login")
    session.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        secure=request.app.state.settings.cookie_secure,
        max_age=43200,
        path="/",
    )
    return public_user(user)


@router.get("/auth/me")
def me(user: Actor):
    return public_user(user)


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: Actor, session: DB):
    session.execute(
        delete(AuthSession).where(
            AuthSession.token_hash == token_hash(request.cookies.get(COOKIE_NAME, ""))
        )
    )
    audit(session, user, "auth.logout")
    session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/cases")
def cases(user: Actor, session: DB):
    query = select(AssessmentCase).where(AssessmentCase.organization_id == user.organization_id)
    if user.role == "analyst":
        query = query.where(AssessmentCase.owner_id == user.id)
    return [
        public_case(case)
        for case in session.scalars(query.order_by(AssessmentCase.created_at.desc()))
    ]


@router.post("/cases", status_code=201)
def create_case(body: CaseCreate, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    case = AssessmentCase(
        organization_id=user.organization_id,
        owner_id=user.id,
        name=body.name,
        counterparty_name=body.counterparty_name,
        relationship=body.relationship.model_dump(),
    )
    session.add(case)
    session.flush()
    audit(session, user, "case.created", case_id=case.id)
    session.commit()
    return public_case(case)


@router.get("/cases/{case_id}")
def case_detail(case_id: UUID, user: Actor, session: DB):
    return public_case(get_case(session, user, case_id))


@router.patch("/cases/{case_id}")
def patch_case(case_id: UUID, body: CasePatch, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    case = get_case(session, user, case_id)
    if body.name is not None:
        case.name = body.name
    if body.relationship is not None:
        case.relationship = body.relationship.model_dump()
    case.updated_at = datetime.now(UTC)
    audit(session, user, "case.updated", case_id=case.id)
    session.commit()
    return public_case(case)


@router.get("/documents")
def documents(user: Actor, session: DB, case_id: UUID | None = None):
    if case_id:
        get_case(session, user, case_id)
    query = (
        select(Document)
        .where(Document.organization_id == user.organization_id, Document.case_id == case_id)
        .order_by(Document.created_at.desc())
    )
    return [public_document(document) for document in session.scalars(query)]


@router.post("/documents", status_code=201)
def upload_document(
    request: Request,
    user: Actor,
    session: DB,
    file: Annotated[UploadFile, File()],
    kind: Annotated[Literal["policy", "evidence"], Form()],
    case_id: Annotated[UUID | None, Form()] = None,
    evidence_type: Annotated[Literal["declaration", "independent"], Form()] = "declaration",
):
    require_roles(user, *WRITE_ROLES)
    if (kind == "policy" and case_id is not None) or (kind == "evidence" and case_id is None):
        raise HTTPException(
            422, "Policy documents are organization scoped; evidence requires a case"
        )
    if case_id:
        get_case(session, user, case_id)
    document, created = ingest(
        session,
        user,
        read_upload(file),
        file.filename or "document.txt",
        kind,
        case_id,
        request.app.state.settings.storage_path,
        evidence_type=evidence_type,
    )
    if created:
        audit(
            session,
            user,
            "document.uploaded",
            case_id=case_id,
            details={
                "document_id": str(document.id),
                "sha256": document.sha256,
                "version": document.version,
            },
        )
    session.commit()
    return {**public_document(document), "deduplicated": not created}


@router.get("/documents/{document_id}")
def document_detail(document_id: UUID, user: Actor, session: DB):
    document = document_for(session, user, document_id)
    return {**public_document(document), "chunks": chunks_for(session, [document])}


@router.get("/documents/{document_id}/download")
def download_document(document_id: UUID, request: Request, user: Actor, session: DB):
    document = document_for(session, user, document_id)
    path = Path(request.app.state.settings.storage_path) / document.storage_key
    if not path.is_file():
        raise HTTPException(404, "Original file unavailable")
    return FileResponse(
        path,
        media_type=document.media_type,
        filename=document.filename,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )


@router.delete("/documents/{document_id}")
def delete_document(document_id: UUID, request: Request, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    document = document_for(session, user, document_id)
    # A lock prevents deletion during new policy/run snapshot creation.
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"references:{user.organization_id}"},
    )
    policies = session.scalars(
        select(PolicySetVersion).where(PolicySetVersion.organization_id == user.organization_id)
    )
    if any(str(document.id) in policy.document_ids for policy in policies):
        raise HTTPException(409, "Document version retained by a policy")
    snapshots = session.scalars(
        select(AnalysisRun.input_snapshot).where(
            AnalysisRun.organization_id == user.organization_id
        )
    )
    if any(
        any(chunk.get("document_id") == str(document.id) for chunk in snapshot.get("chunks", []))
        for snapshot in snapshots
    ):
        # Every checkpoint is tied to a retained AnalysisRun, so this protects it too.
        raise HTTPException(409, "Document version retained by an analysis or checkpoint")
    path = Path(request.app.state.settings.storage_path) / document.storage_key
    audit(
        session,
        user,
        "document.deleted",
        case_id=document.case_id,
        details={"document_id": str(document.id), "sha256": document.sha256},
    )
    session.delete(document)
    session.commit()
    path.unlink(missing_ok=True)
    return {"ok": True}


@router.get("/policies")
def policies(user: Actor, session: DB):
    return [
        public_policy(policy)
        for policy in session.scalars(
            select(PolicySetVersion)
            .where(PolicySetVersion.organization_id == user.organization_id)
            .order_by(PolicySetVersion.created_at.desc())
        )
    ]


def reference_lock(session, user):
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"references:{user.organization_id}"},
    )


def next_policy_version(session, user, name):
    return (
        session.scalar(
            select(func.max(PolicySetVersion.version)).where(
                PolicySetVersion.organization_id == user.organization_id,
                PolicySetVersion.name == name,
            )
        )
        or 0
    ) + 1


@router.post("/policies/propose", status_code=201)
def propose_policy(body: PolicyProposal, request: Request, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    reference_lock(session, user)
    from counterparty.analysis import propose_requirements

    documents = [document_for(session, user, value) for value in dict.fromkeys(body.document_ids)]
    if any(document.kind != "policy" for document in documents):
        raise HTTPException(422, "Only policy documents can define requirements")
    chunks = chunks_for(session, documents)
    proposal_metrics = {}
    requirements = validated_requirements(
        propose_requirements(
            chunks, mode=request.app.state.settings.model_mode, metrics=proposal_metrics
        ),
        chunks,
    )
    policy = PolicySetVersion(
        organization_id=user.organization_id,
        name=body.name,
        version=next_policy_version(session, user, body.name),
        status="draft",
        document_ids=[str(document.id) for document in documents],
        requirements=requirements,
        created_by=user.id,
    )
    session.add(policy)
    session.flush()
    audit(
        session,
        user,
        "policy.proposed",
        details={"policy_id": str(policy.id), "model_metrics": proposal_metrics},
    )
    session.commit()
    return public_policy(policy)


@router.get("/policies/{policy_id}")
def policy_detail(policy_id: UUID, user: Actor, session: DB):
    return public_policy(policy_for(session, user, policy_id))


@router.put("/policies/{policy_id}/requirements")
def edit_requirements(policy_id: UUID, body: RequirementEdit, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    policy = policy_for(session, user, policy_id, lock=True)
    if policy.status != "draft":
        raise HTTPException(409, "Approved policy versions are immutable; clone to edit")
    chunks = chunks_for(session, policy_documents(session, user, policy))
    policy.requirements = validated_requirements(
        [requirement.model_dump(mode="json") for requirement in body.requirements], chunks
    )
    audit(session, user, "policy.edited", details={"policy_id": str(policy.id)})
    session.commit()
    return public_policy(policy)


@router.post("/policies/{policy_id}/approve")
def approve_policy(policy_id: UUID, user: Actor, session: DB):
    require_roles(user, *REVIEW_ROLES)
    policy = policy_for(session, user, policy_id, lock=True)
    if policy.status != "draft":
        raise HTTPException(409, "Policy version already approved")
    validated_requirements(
        policy.requirements, chunks_for(session, policy_documents(session, user, policy))
    )
    policy.status = "approved"
    policy.approved_by = user.id
    policy.approved_at = datetime.now(UTC)
    audit(session, user, "policy.approved", details={"policy_id": str(policy.id)})
    session.commit()
    return public_policy(policy)


@router.post("/policies/{policy_id}/clone", status_code=201)
def clone_policy(policy_id: UUID, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    reference_lock(session, user)
    source = policy_for(session, user, policy_id)
    policy = PolicySetVersion(
        organization_id=user.organization_id,
        name=source.name,
        version=next_policy_version(session, user, source.name),
        status="draft",
        document_ids=copy.deepcopy(source.document_ids),
        requirements=copy.deepcopy(source.requirements),
        created_by=user.id,
    )
    session.add(policy)
    session.flush()
    audit(
        session,
        user,
        "policy.cloned",
        details={"policy_id": str(policy.id), "source_policy_id": str(source.id)},
    )
    session.commit()
    return public_policy(policy)


def public_run(session, run):
    value = {
        key: getattr(run, key)
        for key in (
            "id",
            "case_id",
            "policy_version_id",
            "status",
            "input_snapshot",
            "report",
            "retrieval_variant",
            "model_mode",
            "error",
            "attempts",
            "created_at",
            "started_at",
            "finished_at",
        )
    }
    decision = session.scalar(select(Decision).where(Decision.run_id == run.id))
    value["decision"] = (
        None
        if decision is None
        else {
            "id": decision.id,
            "decision": decision.decision,
            "rationale": decision.rationale,
            "actor_id": decision.actor_id,
            "created_at": decision.created_at,
        }
    )
    value["events"] = [
        public_event(event)
        for event in session.scalars(
            select(AuditEvent).where(AuditEvent.run_id == run.id).order_by(AuditEvent.created_at)
        )
    ]
    return value


def pgvector_scores(session, user, case, documents, requirements):
    """Exact pgvector search over at most 500 immutable evidence chunks.

    The persisted hash embeddings are a deterministic demo feature representation,
    not a learned semantic model. Retaining every bounded candidate preserves the
    same lexical + cosine ranking used by the offline evaluation pipeline.
    """
    from counterparty.analysis import EMBEDDING_MODEL, embed_text

    result = {}
    for requirement in requirements:
        query = embed_text(requirement["title"] + " " + requirement["field"])
        distance = DocumentChunk.embedding.cosine_distance(query).label("distance")
        rows = session.execute(
            select(DocumentChunk.id, distance)
            .where(
                DocumentChunk.organization_id == user.organization_id,
                DocumentChunk.case_id == case.id,
                DocumentChunk.document_id.in_([document.id for document in documents]),
                DocumentChunk.embedding_model == EMBEDDING_MODEL,
            )
            .order_by(distance, DocumentChunk.id)
            .limit(500)
        )
        result[requirement["id"]] = {
            str(chunk_id): (1.0 - value if math.isfinite(value) else 0.0)
            for chunk_id, value in rows
        }
    return result


@router.get("/cases/{case_id}/runs")
def runs(case_id: UUID, user: Actor, session: DB):
    get_case(session, user, case_id)
    return [
        public_run(session, run)
        for run in session.scalars(
            select(AnalysisRun)
            .where(
                AnalysisRun.case_id == case_id, AnalysisRun.organization_id == user.organization_id
            )
            .order_by(AnalysisRun.created_at.desc())
        )
    ]


@router.post("/cases/{case_id}/runs", status_code=201)
def create_run(case_id: UUID, body: RunCreate, request: Request, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    reference_lock(session, user)
    case = get_case(session, user, case_id)
    policy = policy_for(session, user, body.policy_version_id)
    if policy.status != "approved":
        raise HTTPException(409, "Analysis requires an approved policy version")
    policy_docs = policy_documents(session, user, policy)
    candidates = session.scalars(
        select(Document)
        .where(
            Document.organization_id == user.organization_id,
            Document.case_id == case_id,
            Document.kind == "evidence",
        )
        .order_by(Document.version.desc(), Document.created_at.desc())
    )
    current = {}
    for document in candidates:
        current.setdefault(document.filename, document)
    chunks = chunks_for(session, [*policy_docs, *current.values()])
    if sum(chunk["kind"] == "evidence" for chunk in chunks) > 500:
        raise HTTPException(422, "Analysis supports at most 500 evidence chunks")
    validated_requirements(policy.requirements, chunks_for(session, policy_docs))
    snapshot = {
        "case": {
            "id": str(case.id),
            "name": case.name,
            "counterparty_name": case.counterparty_name,
            "relationship": copy.deepcopy(case.relationship),
        },
        "policy": {"id": str(policy.id), "name": policy.name, "version": policy.version},
        "requirements": copy.deepcopy(policy.requirements),
        "chunks": chunks,
        "model_mode": request.app.state.settings.model_mode,
    }
    if body.retrieval_variant == "hybrid":
        from counterparty.analysis import EMBEDDING_MODEL

        snapshot["retrieval_scores"] = pgvector_scores(
            session, user, case, list(current.values()), policy.requirements
        )
        eligible_ids = {chunk["id"] for chunk in chunks if chunk["kind"] == "evidence"}
        if any(set(scores) != eligible_ids for scores in snapshot["retrieval_scores"].values()):
            raise HTTPException(422, "Evidence embeddings are incompatible; re-ingest documents")
        snapshot["retrieval_config"] = {
            "backend": "pgvector-exact",
            "embedding_model": EMBEDDING_MODEL,
            "dimension": 128,
            "limit": 500,
            "version": "hybrid-v1",
        }
    run = AnalysisRun(
        organization_id=user.organization_id,
        case_id=case.id,
        created_by=user.id,
        policy_version_id=policy.id,
        status="queued",
        input_snapshot=snapshot,
        retrieval_variant=body.retrieval_variant,
        model_mode=request.app.state.settings.model_mode,
    )
    session.add(run)
    session.flush()
    audit(
        session,
        user,
        "analysis.queued",
        case_id=case.id,
        run_id=run.id,
        details={"policy_version_id": str(policy.id), "retrieval_variant": body.retrieval_variant},
    )
    session.commit()
    return public_run(session, run)


@router.get("/runs/{run_id}")
def run_detail(run_id: UUID, user: Actor, session: DB):
    return public_run(session, run_for(session, user, run_id))


@router.post("/runs/{run_id}/decision", status_code=201)
def decide(run_id: UUID, body: DecisionCreate, user: Actor, session: DB):
    require_roles(user, *REVIEW_ROLES)
    run = run_for(session, user, run_id, lock=True)
    if run.status != "awaiting_review" or session.scalar(
        select(Decision).where(Decision.run_id == run.id)
    ):
        raise HTTPException(409, "Decision requires an undecided report awaiting review")
    decision = Decision(
        organization_id=user.organization_id,
        run_id=run.id,
        actor_id=user.id,
        decision=body.decision,
        rationale=body.rationale,
    )
    session.add(decision)
    run.status = "completed"
    run.finished_at = datetime.now(UTC)
    audit(
        session,
        user,
        "analysis.decision",
        case_id=run.case_id,
        run_id=run.id,
        details={"decision": body.decision, "rationale": body.rationale},
    )
    session.commit()
    return public_run(session, run)


def public_event(event):
    return {
        key: getattr(event, key)
        for key in ("id", "actor_id", "case_id", "run_id", "event", "details", "created_at")
    }


@router.get("/audit")
def audit_events(user: Actor, session: DB, case_id: UUID | None = None):
    query = select(AuditEvent).where(AuditEvent.organization_id == user.organization_id)
    if case_id:
        get_case(session, user, case_id)
        query = query.where(AuditEvent.case_id == case_id)
    elif user.role == "analyst":
        own_cases = select(AssessmentCase.id).where(
            AssessmentCase.owner_id == user.id,
            AssessmentCase.organization_id == user.organization_id,
        )
        query = query.where(
            or_(
                AuditEvent.case_id.in_(own_cases),
                (AuditEvent.case_id.is_(None)) & (AuditEvent.actor_id == user.id),
            )
        )
    return [
        public_event(event)
        for event in session.scalars(query.order_by(AuditEvent.created_at.desc()).limit(500))
    ]
