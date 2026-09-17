"""Analyses endpoints."""

import copy
import os
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from counterparty.api.common import (
    DB,
    Actor,
    policy_documents,
    policy_for,
    public_event,
    reference_lock,
    run_for,
    validated_requirements,
)
from counterparty.deletion import deletion_lock, purge_run
from counterparty.documents import chunks_for
from counterparty.models import AnalysisRun, AuditEvent, Decision, Document, User
from counterparty.schemas import DecisionCreate, InformationRequestDraft, RunCreate
from counterparty.security import (
    REVIEW_ROLES,
    WRITE_ROLES,
    audit,
    case_is_decided,
    get_case,
    require_case_write,
    require_roles,
)

router = APIRouter()


def retry_blocked_reason(run, decision):
    if run.status != "failed" or run.input_snapshot.get("assessment_version") != "semantic-v2":
        return "Only a failed semantic assessment can be resumed"
    if decision:
        return "A reviewed assessment cannot be resumed"
    progress = run.assessment_progress or {}
    if any(
        count >= 3 and key not in progress.get("completed_ids", [])
        for key, count in progress.get("attempts", {}).items()
    ):
        return "Requirement attempt limit reached; review the cause before creating a new analysis"
    return None


def public_run(session, run):
    value = {
        key: getattr(run, key)
        for key in (
            "id",
            "case_id",
            "policy_version_id",
            "status",
            "input_snapshot",
            "retrieval_snapshot",
            "information_request_draft",
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
    value["retry_blocked_reason"] = retry_blocked_reason(run, decision)
    value["case_is_decided"] = case_is_decided(session, run.case_id)
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
        public_event(event, email)
        for event, email in session.execute(
            select(AuditEvent, User.email)
            .outerjoin(
                User,
                (User.id == AuditEvent.actor_id)
                & (User.organization_id == AuditEvent.organization_id),
            )
            .where(AuditEvent.run_id == run.id)
            .order_by(AuditEvent.created_at)
        )
    ]
    progress = run.assessment_progress or {}
    value["progress"] = {
        "completed": progress.get("completed", 0),
        "total": progress.get("total", len(run.input_snapshot.get("requirements", []))),
        "current_requirement_id": progress.get("current_requirement_id"),
        "error": run.error,
    }
    return value


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
    require_case_write(session, user, case_id)
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
        "assessment_version": "semantic-v2",
        "model_name": os.getenv("GEMINI_MODEL", "")
        if request.app.state.settings.model_mode == "gemini"
        else "semantic-demo-v2",
        "requirement_embeddings": copy.deepcopy(policy.requirement_embeddings),
    }
    from counterparty.analysis.semantic import normalize_requirement

    snapshot["requirements"] = [normalize_requirement(r) for r in snapshot["requirements"]]
    from counterparty.embedding_config import CONFIG, FINGERPRINT

    snapshot["retrieval_algorithm"] = CONFIG["retrieval"]
    if any(
        doc.index_status != "ready" or doc.index_config != FINGERPRINT for doc in current.values()
    ) or any(
        chunk["embedding_model"] != FINGERPRINT for chunk in chunks if chunk["kind"] == "evidence"
    ):
        raise HTTPException(
            409,
            "Evidence indexing is pending or incompatible. Wait for ready status or request "
            "reindex.",
        )
    snapshot["retrieval_config"] = copy.deepcopy(CONFIG)
    snapshot["retrieval_fingerprint"] = FINGERPRINT
    run = AnalysisRun(
        organization_id=user.organization_id,
        case_id=case.id,
        created_by=user.id,
        policy_version_id=policy.id,
        status="queued",
        input_snapshot=snapshot,
        retrieval_variant="hybrid",
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
        details={"policy_version_id": str(policy.id), "retrieval_variant": "hybrid"},
    )
    session.commit()
    return public_run(session, run)


@router.get("/runs/{run_id}")
def run_detail(run_id: UUID, user: Actor, session: DB):
    return public_run(session, run_for(session, user, run_id))


@router.post("/runs/{run_id}/retry")
def retry_run(run_id: UUID, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    reference_lock(session, user)
    run = run_for(session, user, run_id, lock=True)
    require_case_write(session, user, run.case_id)
    if run.status != "failed" or run.input_snapshot.get("assessment_version") != "semantic-v2":
        raise HTTPException(409, "Only a failed semantic assessment can be resumed")
    if session.scalar(select(Decision).where(Decision.run_id == run.id)):
        raise HTTPException(409, "A reviewed assessment cannot be resumed")
    reason = retry_blocked_reason(run, decision=False)
    if reason:
        raise HTTPException(409, reason)
    run.status = "queued"
    run.error = None
    run.attempts = 0
    run.lease_owner = None
    run.lease_expires_at = None
    audit(
        session,
        user,
        "analysis.resumed",
        case_id=run.case_id,
        run_id=run.id,
        details={"completed": (run.assessment_progress or {}).get("completed", 0)},
    )
    session.commit()
    return public_run(session, run)


@router.put("/runs/{run_id}/information-request-draft")
def save_information_request_draft(
    run_id: UUID, body: InformationRequestDraft, user: Actor, session: DB
):
    reference_lock(session, user)
    run = run_for(session, user, run_id, lock=True)
    require_case_write(session, user, run.case_id)
    if run.status != "awaiting_review" or session.scalar(
        select(Decision.id).where(Decision.run_id == run.id)
    ):
        raise HTTPException(409, "Draft requires an undecided report awaiting review")
    if user.role == "analyst" and run.information_request_draft is not None:
        raise HTTPException(403, "Submitted information requests can only be edited by a reviewer")
    run.information_request_draft = {
        "text": body.text,
        "actor_id": str(user.id),
        "actor_email": user.email,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    audit(
        session,
        user,
        "information_request.draft_saved",
        run.case_id,
        run.id,
        details={"text": body.text},
    )
    session.commit()
    return public_run(session, run)


@router.post("/runs/{run_id}/decision", status_code=201)
def decide(run_id: UUID, body: DecisionCreate, user: Actor, session: DB):
    require_roles(user, *REVIEW_ROLES)
    reference_lock(session, user)
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
    run.report = {**run.report, "workflow_complete": True}
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


@router.delete("/runs/{run_id}", tags=["deletion"])
def delete_run(run_id: UUID, user: Actor, session: DB):
    deletion_lock(session, user)
    run = run_for(session, user, run_id)
    case_id = run.case_id
    require_case_write(session, user, case_id)
    if user.role == "analyst" and session.scalar(
        select(Decision.id).where(Decision.run_id == run.id)
    ):
        raise HTTPException(403, "Reviewed reports cannot be deleted by analysts.")
    purge_run(session, user, run)
    audit(session, user, "run.deleted", case_id=case_id, details={"resource_id": str(run_id)})
    session.commit()
    return {"ok": True}
