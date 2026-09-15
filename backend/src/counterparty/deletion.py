"""Explicit removal of persisted resources and their local dependent content."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from counterparty.models import (
    AnalysisRun,
    ApprovalRequest,
    AuditEvent,
    Decision,
    Document,
    IntegrationCall,
)
from counterparty.routes import DB, Actor, policy_for, run_for
from counterparty.security import WRITE_ROLES, audit, get_case, require_roles
from counterparty.worker import lock_key

router = APIRouter(prefix="/api", tags=["deletion"])


def deletion_lock(session, user):
    require_roles(user, *WRITE_ROLES)
    if not session.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"references:{user.organization_id}"},
    ):
        raise HTTPException(
            409, "Another operation is active. Wait for it to finish before deleting."
        )


def lock_record(session, record):
    try:
        with session.begin_nested():
            session.refresh(record, with_for_update={"nowait": True})
    except OperationalError as error:
        if getattr(error.orig, "sqlstate", None) != "55P03":
            raise
        raise HTTPException(409, "This item is being processed. Wait before deleting.") from None


def purge_events(session, user, field, resource_id):
    session.execute(
        delete(AuditEvent).where(
            AuditEvent.organization_id == user.organization_id,
            AuditEvent.details[field].astext == str(resource_id),
        )
    )


def guard_document(session, document):
    lock_record(session, document)
    if (
        document.index_status == "indexing"
        and document.index_lease_expires_at
        and document.index_lease_expires_at > datetime.now(UTC)
    ):
        raise HTTPException(409, "Document indexing is active. Wait before deleting.")


def purge_approval(session, user, approval):
    lock_record(session, approval)
    if approval.status == "executing":
        raise HTTPException(409, "Ticket creation is active. Wait before deleting.")
    session.execute(delete(IntegrationCall).where(IntegrationCall.approval_id == approval.id))
    purge_events(session, user, "approval_id", approval.id)
    session.delete(approval)
    session.flush()


def purge_run(session, user, run):
    if not session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key(run.id)}
    ):
        raise HTTPException(409, "Analysis is active. Wait before deleting.")
    lock_record(session, run)
    if run.status == "running" and (
        run.lease_expires_at is None or run.lease_expires_at > datetime.now(UTC)
    ):
        raise HTTPException(409, "Analysis is running. Wait for it to finish before deleting.")
    for approval in session.scalars(
        select(ApprovalRequest).where(ApprovalRequest.run_id == run.id)
    ).all():
        purge_approval(session, user, approval)
    session.execute(delete(Decision).where(Decision.run_id == run.id))
    session.execute(delete(AuditEvent).where(AuditEvent.run_id == run.id))
    # LangGraph tables are installed by the worker, and may not exist on a fresh API.
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        if session.scalar(text("SELECT to_regclass(:name)"), {"name": table}):
            session.execute(
                text(f"DELETE FROM {table} WHERE thread_id = :thread"), {"thread": str(run.id)}
            )
    session.delete(run)
    session.flush()


@router.delete("/runs/{run_id}")
def delete_run(run_id: UUID, user: Actor, session: DB):
    deletion_lock(session, user)
    run = run_for(session, user, run_id)
    case_id = run.case_id
    purge_run(session, user, run)
    audit(session, user, "run.deleted", case_id=case_id, details={"resource_id": str(run_id)})
    session.commit()
    return {"ok": True}


@router.delete("/cases/{case_id}")
def delete_case(case_id: UUID, request: Request, user: Actor, session: DB):
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


@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: UUID, user: Actor, session: DB):
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


@router.delete("/approvals/{approval_id}")
def delete_approval(approval_id: UUID, user: Actor, session: DB):
    from counterparty.integrations import get_approval

    deletion_lock(session, user)
    approval, run = get_approval(session, user, approval_id)
    purge_approval(session, user, approval)
    audit(
        session,
        user,
        "ticket.local_record_deleted",
        case_id=run.case_id,
        run_id=run.id,
        details={"resource_id": str(approval_id)},
    )
    session.commit()
    return {"ok": True}


def queue_file_cleanup(session, user, storage_keys):
    if storage_keys:
        event = audit(
            session, user, "storage.cleanup_pending", details={"storage_keys": storage_keys}
        )
        session.flush()
        return event.id


def cleanup_files(engine, storage_path):
    """Retry only explicitly deleted originals; DB tombstones survive crashes and I/O errors."""
    with Session(engine) as session:
        pending = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.event == "storage.cleanup_pending")
            .with_for_update(skip_locked=True)
        ).all()
        for event in pending:
            try:
                for key in event.details["storage_keys"]:
                    (Path(storage_path) / key).unlink(missing_ok=True)
            except OSError:
                continue
            session.delete(event)
        session.commit()
        return set(
            session.scalars(
                select(AuditEvent.id).where(AuditEvent.event == "storage.cleanup_pending")
            )
        )
