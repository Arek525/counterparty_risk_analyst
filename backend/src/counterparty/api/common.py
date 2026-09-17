"""Shared API dependencies, scoped lookups and source validation."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from counterparty.models import AnalysisRun, Document, PolicySetVersion, User
from counterparty.schemas import NarrativeRequirement, Requirement
from counterparty.security import current_user, get_case, get_session

DB = Annotated[Session, Depends(get_session)]
Actor = Annotated[User, Depends(current_user)]


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


def validated_requirements(requirements, chunks):
    from counterparty.analysis import validate_requirements
    from counterparty.analysis.semantic import validate_narrative_requirements

    try:
        if requirements and all("description" in item for item in requirements):
            parsed = [
                NarrativeRequirement.model_validate(item).model_dump(mode="json")
                for item in requirements
            ]
            return validate_narrative_requirements(parsed, chunks)
        parsed = [Requirement.model_validate(item).model_dump(mode="json") for item in requirements]
        validate_requirements(parsed, chunks)
        return parsed
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, "Invalid requirement schema or unresolved policy source") from exc


def policy_documents(session, user, policy):
    documents = [document_for(session, user, UUID(value)) for value in policy.document_ids]
    if any(document.kind != "policy" or document.case_id is not None for document in documents):
        raise HTTPException(422, "Policy must reference organization policy documents")
    return documents


def reference_lock(session, user):
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"references:{user.organization_id}"},
    )


def public_event(event, actor_email=None):
    return {
        "actor_email": actor_email,
        **{
            key: getattr(event, key)
            for key in ("id", "actor_id", "case_id", "run_id", "event", "details", "created_at")
        },
    }
