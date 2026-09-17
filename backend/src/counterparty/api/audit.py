"""Audit endpoints."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import or_, select

from counterparty.api.common import DB, Actor, public_event
from counterparty.models import AssessmentCase, AuditEvent, User
from counterparty.security import get_case

router = APIRouter()


@router.get("/audit")
def audit_events(user: Actor, session: DB, case_id: UUID | None = None):
    query = select(AuditEvent).where(AuditEvent.organization_id == user.organization_id)
    if case_id:
        get_case(session, user, case_id)
        query = query.where(AuditEvent.case_id == case_id)
    elif user.role == "analyst":
        organization_cases = select(AssessmentCase.id).where(
            AssessmentCase.organization_id == user.organization_id,
        )
        query = query.where(
            or_(
                AuditEvent.case_id.in_(organization_cases),
                (AuditEvent.case_id.is_(None)) & (AuditEvent.actor_id == user.id),
            )
        )
    return [
        public_event(event, email)
        for event, email in session.execute(
            query.add_columns(User.email)
            .outerjoin(
                User,
                (User.id == AuditEvent.actor_id)
                & (User.organization_id == AuditEvent.organization_id),
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(500)
        )
    ]
