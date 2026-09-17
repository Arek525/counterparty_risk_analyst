"""Explicit removal of persisted resources and their local dependent content."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from counterparty.models import AuditEvent, Decision
from counterparty.security import WRITE_ROLES, audit, require_roles
from counterparty.worker import lock_key


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
    session.execute(delete(Decision).where(Decision.run_id == run.id))
    session.execute(delete(AuditEvent).where(AuditEvent.run_id == run.id))
    session.delete(run)
    session.flush()


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
