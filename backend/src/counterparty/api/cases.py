"""Cases endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import delete, select

from counterparty.api.common import DB, Actor, reference_lock
from counterparty.deletion import (
    cleanup_files,
    deletion_lock,
    guard_document,
    lock_record,
    purge_events,
    purge_run,
    queue_file_cleanup,
)
from counterparty.models import AnalysisRun, AssessmentCase, AuditEvent, Document
from counterparty.schemas import CaseCreate, CasePatch
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


def public_case(case, session):
    value = {
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

    value["is_decided"] = case_is_decided(session, case.id)
    return value


@router.get("/cases")
def cases(user: Actor, session: DB):
    query = select(AssessmentCase).where(AssessmentCase.organization_id == user.organization_id)
    return [
        public_case(case, session)
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
    return public_case(case, session)


@router.get("/cases/{case_id}")
def case_detail(case_id: UUID, user: Actor, session: DB):
    return public_case(get_case(session, user, case_id), session)


@router.patch("/cases/{case_id}")
def patch_case(case_id: UUID, body: CasePatch, user: Actor, session: DB):
    require_roles(user, *WRITE_ROLES)
    reference_lock(session, user)
    case = get_case(session, user, case_id)
    require_case_write(session, user, case_id)
    if body.name is not None:
        case.name = body.name
    if body.relationship is not None:
        case.relationship = body.relationship.model_dump()
    case.updated_at = datetime.now(UTC)
    audit(session, user, "case.updated", case_id=case.id)
    session.commit()
    return public_case(case, session)


@router.delete("/cases/{case_id}", tags=["deletion"])
def delete_case(case_id: UUID, request: Request, user: Actor, session: DB):
    require_roles(user, *REVIEW_ROLES)
    deletion_lock(session, user)
    case = get_case(session, user, case_id)
    lock_record(session, case)
    documents = session.scalars(select(Document).where(Document.case_id == case.id)).all()
    for document in documents:
        guard_document(session, document)
    for run in session.scalars(select(AnalysisRun).where(AnalysisRun.case_id == case.id)).all():
        purge_run(session, user, run)
    storage_keys = []
    for document in documents:
        storage_keys.append(document.storage_key)
        purge_events(session, user, "document_id", document.id)
        session.delete(document)
    session.flush()
    session.execute(delete(AuditEvent).where(AuditEvent.case_id == case.id))
    session.delete(case)
    audit(session, user, "case.deleted", details={"resource_id": str(case_id)})
    cleanup_id = queue_file_cleanup(session, user, storage_keys)
    session.commit()
    pending = cleanup_files(request.app.state.engine, request.app.state.settings.storage_path)
    return {"ok": True, "cleanup_pending": cleanup_id in pending}
