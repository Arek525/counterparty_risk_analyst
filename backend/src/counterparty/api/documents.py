"""Documents endpoints."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from counterparty.api.common import DB, Actor, document_for, reference_lock
from counterparty.documents import chunks_for, ingest, read_upload
from counterparty.models import AnalysisRun, Document, PolicySetVersion
from counterparty.security import (
    REVIEW_ROLES,
    WRITE_ROLES,
    audit,
    case_is_decided,
    get_case,
    require_case_write,
    require_document_write,
    require_roles,
)

router = APIRouter()


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
            "index_status",
            "index_config",
            "index_attempts",
            "index_error",
            "indexed_at",
        )
    }


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


@router.get("/embedding-status")
def embedding_status(user: Actor, session: DB):
    from counterparty.embedding_config import CONFIG, FINGERPRINT
    from counterparty.models import WorkerModelState

    state = session.get(WorkerModelState, "local-embeddings")
    fresh = bool(
        state
        and state.config == FINGERPRINT
        and (datetime.now(UTC) - state.heartbeat_at).total_seconds() < 30
    )
    return {
        "status": state.status if fresh else "unavailable",
        "fresh": fresh,
        "config": CONFIG,
        "fingerprint": FINGERPRINT,
        "heartbeat_at": state.heartbeat_at if state else None,
        "error": state.error if state else None,
    }


@router.post("/documents/{document_id}/reindex")
def reindex_document(document_id: UUID, user: Actor, session: DB):
    from counterparty.indexing import request_reindex

    require_roles(user, *WRITE_ROLES)
    reference_lock(session, user)
    document = document_for(session, user, document_id)
    require_document_write(session, user, document)
    session.refresh(document, with_for_update=True)
    if request_reindex(session, document):
        audit(
            session,
            user,
            "document.reindex_requested",
            case_id=document.case_id,
            details={"document_id": str(document.id), "config": document.index_config},
        )
    session.commit()
    return public_document(document)


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
    reference_lock(session, user)
    if (kind == "policy" and case_id is not None) or (kind == "evidence" and case_id is None):
        raise HTTPException(
            422, "Policy documents are organization scoped; evidence requires a case"
        )
    if kind == "policy":
        require_roles(user, *REVIEW_ROLES)
    if case_id:
        require_case_write(session, user, case_id)
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
def document_detail(document_id: UUID, request: Request, user: Actor, session: DB):
    document = document_for(session, user, document_id)
    from counterparty.documents import original_text

    return {
        **public_document(document),
        "chunks": chunks_for(session, [document]),
        "text": original_text(document, request.app.state.settings.storage_path),
        "case_is_decided": bool(document.case_id and case_is_decided(session, document.case_id)),
    }


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
    from counterparty.deletion import (
        cleanup_files,
        deletion_lock,
        guard_document,
        purge_events,
        queue_file_cleanup,
    )

    deletion_lock(session, user)
    document = document_for(session, user, document_id)
    require_document_write(session, user, document)
    guard_document(session, document)
    policies = session.scalars(
        select(PolicySetVersion).where(PolicySetVersion.organization_id == user.organization_id)
    )
    if any(str(document.id) in policy.document_ids for policy in policies):
        raise HTTPException(
            409, "Delete policy versions using this document first, then delete the document."
        )
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
        raise HTTPException(
            409, "Delete analyses using this document first, then delete the document."
        )
    cleanup_id = queue_file_cleanup(session, user, [document.storage_key])
    purge_events(session, user, "document_id", document.id)
    audit(
        session,
        user,
        "document.deleted",
        case_id=document.case_id,
        details={"resource_id": str(document.id)},
    )
    session.delete(document)
    session.commit()
    pending = cleanup_files(request.app.state.engine, request.app.state.settings.storage_path)
    return {"ok": True, "cleanup_pending": cleanup_id in pending}
