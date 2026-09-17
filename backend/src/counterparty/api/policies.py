"""Policies endpoints."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from counterparty.api.common import (
    DB,
    Actor,
    document_for,
    policy_documents,
    policy_for,
    reference_lock,
    validated_requirements,
)
from counterparty.deletion import deletion_lock, lock_record, purge_events
from counterparty.documents import chunks_for
from counterparty.models import AnalysisRun, AuditEvent, PolicySetVersion
from counterparty.schemas import PolicyProposal
from counterparty.security import REVIEW_ROLES, audit, require_roles

router = APIRouter()


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
            "extraction_status",
            "extraction_error",
            "requirement_index_status",
            "requirement_index_error",
        )
    }


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
    require_roles(user, *REVIEW_ROLES)
    reference_lock(session, user)
    from counterparty.analysis.adapters import ModelError
    from counterparty.analysis.semantic import propose_narrative_requirements

    documents = [document_for(session, user, value) for value in dict.fromkeys(body.document_ids)]
    if any(document.kind != "policy" or document.case_id is not None for document in documents):
        raise HTTPException(422, "Only policy documents can define requirements")
    extraction_key = hashlib.sha256(
        json.dumps(sorted(str(d.id) for d in documents)).encode()
    ).hexdigest()
    cached = session.scalar(
        select(PolicySetVersion)
        .where(
            PolicySetVersion.organization_id == user.organization_id,
            PolicySetVersion.extraction_key == extraction_key,
        )
        .order_by(PolicySetVersion.created_at.desc())
    )
    if cached is not None:
        if not body.regenerate:
            return public_policy(cached)
        if cached.extraction_status == "extracting" and datetime.now(
            UTC
        ) - cached.created_at < timedelta(seconds=180):
            raise HTTPException(409, "Extraction is still running. Wait before regenerating.")
    chunks = chunks_for(session, documents)
    policy = PolicySetVersion(
        organization_id=user.organization_id,
        name=body.name,
        version=next_policy_version(session, user, body.name),
        status="draft",
        document_ids=[str(document.id) for document in documents],
        requirements=[],
        extraction_key=extraction_key,
        extraction_status="extracting",
        created_by=user.id,
    )
    session.add(policy)
    session.flush()
    audit(session, user, "policy.extraction_started", details={"policy_id": str(policy.id)})
    session.commit()
    # The saved placeholder deduplicates concurrent clicks, including a disconnected client.
    # Failed/abandoned attempts are visible and require explicit regeneration.
    proposal_metrics = {}
    # Hold the row through inference: deletion can distinguish a live call from
    # an abandoned extracting placeholder after its existing 180-second timeout.
    session.refresh(policy, with_for_update=True)
    try:
        requirements = validated_requirements(
            propose_narrative_requirements(
                chunks,
                mode=request.app.state.settings.model_mode,
                metrics=proposal_metrics,
            ),
            chunks,
        )
        session.refresh(policy, with_for_update=True)
        policy.requirements = requirements
        policy.extraction_status = "ready"
    except (ModelError, HTTPException, ValueError, TypeError) as error:
        policy.extraction_status = "error"
        policy.extraction_error = (
            str(error)
            if isinstance(error, ModelError)
            else "Extraction failed validation. Review the source and explicitly regenerate."
        )
    audit(
        session,
        user,
        "policy.proposed" if policy.extraction_status == "ready" else "policy.extraction_failed",
        details={"policy_id": str(policy.id), "model_metrics": proposal_metrics},
    )
    session.commit()
    return public_policy(policy)


@router.get("/policies/{policy_id}")
def policy_detail(policy_id: UUID, user: Actor, session: DB):
    return public_policy(policy_for(session, user, policy_id))


@router.post("/policies/{policy_id}/approve")
def approve_policy(policy_id: UUID, user: Actor, session: DB):
    require_roles(user, *REVIEW_ROLES)
    policy = policy_for(session, user, policy_id, lock=True)
    if policy.status != "draft" or policy.extraction_status != "ready":
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


@router.delete("/policies/{policy_id}", tags=["deletion"])
def delete_policy(policy_id: UUID, user: Actor, session: DB):
    require_roles(user, *REVIEW_ROLES)
    deletion_lock(session, user)
    policy = policy_for(session, user, policy_id)
    lock_record(session, policy)
    if policy.extraction_status == "extracting" and datetime.now(
        UTC
    ) - policy.created_at < timedelta(seconds=180):
        raise HTTPException(409, "Policy extraction is active. Wait before deleting.")
    if session.scalar(
        select(AnalysisRun.id).where(AnalysisRun.policy_version_id == policy.id).limit(1)
    ):
        raise HTTPException(
            409, "Delete analyses using this policy version first, then delete the policy."
        )
    if session.scalar(
        select(AuditEvent.id)
        .where(
            AuditEvent.organization_id == user.organization_id,
            AuditEvent.event == "synthetic.policy_seeded",
            AuditEvent.details["policy_id"].astext == str(policy.id),
        )
        .limit(1)
    ):
        audit(session, user, "synthetic.bootstrap_completed")
    purge_events(session, user, "policy_id", policy.id)
    session.delete(policy)
    audit(session, user, "policy.deleted", details={"resource_id": str(policy_id)})
    session.commit()
    return {"ok": True}
