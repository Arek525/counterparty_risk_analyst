"""Approval-scoped, idempotent writes to the local ticketing service."""

import time
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from counterparty.models import AnalysisRun, ApprovalRequest, IntegrationCall, User
from counterparty.routes import reference_lock
from counterparty.security import audit, current_user, get_case, get_session, require_roles
from counterparty.ticket_service import payload_hash

router = APIRouter(prefix="/api", tags=["ticket approvals"])
DB = Annotated[Session, Depends(get_session)]
Actor = Annotated[User, Depends(current_user)]


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)


def scoped_run(session, user, run_id):
    run = session.scalar(
        select(AnalysisRun).where(
            AnalysisRun.id == run_id, AnalysisRun.organization_id == user.organization_id
        )
    )
    if run is None:
        raise HTTPException(404, "Analysis not found")
    get_case(session, user, run.case_id)
    return run


def ensure_current(session, run):
    latest = session.scalar(
        select(AnalysisRun.id)
        .where(AnalysisRun.case_id == run.case_id)
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
        .limit(1)
    )
    if latest != run.id:
        raise HTTPException(
            409, "This analysis has been superseded; propose a ticket for the latest run"
        )


def approval_json(approval, call=None):
    return {
        "id": str(approval.id),
        "run_id": str(approval.run_id),
        "action": approval.action,
        "arguments": approval.arguments,
        "arguments_hash": approval.arguments_hash,
        "status": approval.status,
        "requested_by": str(approval.requested_by),
        "approved_by": str(approval.approved_by) if approval.approved_by else None,
        "expires_at": approval.expires_at.isoformat(),
        "created_at": approval.created_at.isoformat(),
        "ticket": call.response if call else None,
        "error": call.error if call else None,
    }


@router.post("/runs/{run_id}/ticket-proposals", status_code=201)
def propose(run_id: UUID, body: Proposal, session: DB, user: Actor):
    require_roles(user, "analyst", "reviewer", "administrator")
    reference_lock(session, user)
    run = scoped_run(session, user, run_id)
    ensure_current(session, run)
    if run.report is None:
        raise HTTPException(409, "Wait for the analysis report")
    arguments = {
        **body.model_dump(),
        "run_id": str(run.id),
        "organization_id": str(user.organization_id),
    }
    approval = ApprovalRequest(
        organization_id=user.organization_id,
        run_id=run.id,
        requested_by=user.id,
        arguments=arguments,
        arguments_hash=payload_hash(arguments),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    session.add(approval)
    session.flush()
    audit(session, user, "ticket.proposed", run.case_id, run.id, {"approval_id": str(approval.id)})
    session.commit()
    return approval_json(approval)


def get_approval(session, user, approval_id, lock=False):
    query = select(ApprovalRequest).where(
        ApprovalRequest.id == approval_id, ApprovalRequest.organization_id == user.organization_id
    )
    approval = session.scalar(query.with_for_update() if lock else query)
    if approval is None:
        raise HTTPException(404, "Approval not found")
    run = scoped_run(session, user, approval.run_id)
    return approval, run


def validate_approval(session, approval, run):
    ensure_current(session, run)
    if approval.expires_at <= datetime.now(UTC):
        raise HTTPException(409, "Approval expired; create a new proposal")
    if (
        approval.action != "create_ticket"
        or payload_hash(approval.arguments) != approval.arguments_hash
    ):
        raise HTTPException(409, "Approved action or arguments changed")
    if approval.arguments.get("run_id") != str(run.id) or approval.arguments.get(
        "organization_id"
    ) != str(run.organization_id):
        raise HTTPException(409, "Approval scope changed")


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: UUID, session: DB, user: Actor):
    require_roles(user, "reviewer", "administrator")
    reference_lock(session, user)
    approval, run = get_approval(session, user, approval_id, lock=True)
    validate_approval(session, approval, run)
    if approval.status != "proposed":
        raise HTTPException(409, "Proposal already handled")
    approval.status = "approved"
    approval.approved_by = user.id
    approval.approved_at = datetime.now(UTC)
    session.add(
        IntegrationCall(
            organization_id=user.organization_id,
            approval_id=approval.id,
            idempotency_key=str(uuid4()),
            request=dict(approval.arguments),
            status="pending",
        )
    )
    audit(
        session,
        user,
        "ticket.approved",
        run.case_id,
        run.id,
        {"approval_id": str(approval.id), "arguments_hash": approval.arguments_hash},
    )
    session.commit()
    return approval_json(approval)


def validate_receipt(data, call):
    UUID(data["id"])
    if any(
        data.get(field) != call.request[field]
        for field in ("run_id", "organization_id", "title", "body")
    ) or data.get("status") not in {"open", "closed", "in_progress"}:
        raise ValueError("Invalid ticket response")
    return data


def read_receipt(settings, call, client=None):
    owns_client = client is None
    client = client or httpx.Client(timeout=5, follow_redirects=False)
    try:
        response = client.get(
            f"{settings.ticket_service_url.rstrip('/')}/tickets/by-key/{call.idempotency_key}",
            headers={"X-Service-Token": settings.ticket_service_token.get_secret_value()},
        )
        response.raise_for_status()
        return validate_receipt(response.json(), call)
    finally:
        if owns_client:
            client.close()


def send_ticket(settings, call, client=None):
    """Bounded retries reuse a durable key, including after a lost response."""
    owns_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(5, connect=2), follow_redirects=False)
    try:
        while call.attempts < 3:
            call.attempts += 1
            try:
                response = client.post(
                    f"{settings.ticket_service_url.rstrip('/')}/tickets",
                    json=call.request,
                    headers={
                        "Idempotency-Key": call.idempotency_key,
                        "X-Service-Token": settings.ticket_service_token.get_secret_value(),
                    },
                )
                if response.status_code in {429, 502, 503, 504}:
                    raise httpx.TransportError("Transient service failure")
                response.raise_for_status()
                return validate_receipt(response.json(), call)
            except httpx.TransportError:
                if call.attempts >= 3:
                    raise
                time.sleep(0.1 * 2**call.attempts)
    finally:
        if owns_client:
            client.close()
    raise ValueError("Ticket attempt limit exceeded")


@router.post("/approvals/{approval_id}/execute")
def execute(approval_id: UUID, request: Request, session: DB, user: Actor):
    require_roles(user, "reviewer", "administrator")
    reference_lock(session, user)
    approval, run = get_approval(session, user, approval_id, lock=True)
    if approval.approved_by != user.id:
        raise HTTPException(403, "Only the actor who approved this exact action may execute it")
    call = session.scalar(select(IntegrationCall).where(IntegrationCall.approval_id == approval.id))
    if approval.status == "executed" and call and call.status == "succeeded":
        return approval_json(approval, call)
    validate_approval(session, approval, run)
    if approval.status != "approved" or call is None:
        raise HTTPException(409, "An approved proposal is required")
    if call.request != approval.arguments:
        raise HTTPException(409, "Persisted request differs from approved arguments")
    approval.status = "executing"
    try:
        call.response = send_ticket(request.app.state.settings, call)
        call.status = "succeeded"
        call.error = None
        approval.status = "executed"
        audit(
            session,
            user,
            "ticket.created",
            run.case_id,
            run.id,
            {
                "approval_id": str(approval.id),
                "ticket_id": call.response["id"],
                "attempts": call.attempts,
            },
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        call.status = "failed"
        call.error = (
            "Ticket service failed or returned invalid data. No duplicate write will be made."
        )
        approval.status = "failed"
        audit(
            session, user, "ticket.failed", run.case_id, run.id, {"approval_id": str(approval.id)}
        )
    call.updated_at = datetime.now(UTC)
    session.commit()
    return approval_json(approval, call)


@router.post("/approvals/{approval_id}/reconcile")
def reconcile(approval_id: UUID, request: Request, session: DB, user: Actor):
    """Recover a lost receipt using a read only; never repeat an expired write."""
    require_roles(user, "reviewer", "administrator")
    reference_lock(session, user)
    approval, run = get_approval(session, user, approval_id, lock=True)
    if approval.approved_by != user.id:
        raise HTTPException(403, "Only the approving actor may reconcile this action")
    call = session.scalar(select(IntegrationCall).where(IntegrationCall.approval_id == approval.id))
    if approval.status == "executed" and call and call.status == "succeeded":
        return approval_json(approval, call)
    if (
        call is None
        or approval.status != "failed"
        or call.request != approval.arguments
        or payload_hash(call.request) != approval.arguments_hash
    ):
        raise HTTPException(409, "A failed, unchanged approved call is required")
    try:
        call.response = read_receipt(request.app.state.settings, call)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(
            502, "No matching receipt could be confirmed; no new ticket was written"
        ) from None
    call.status = "succeeded"
    call.error = None
    call.updated_at = datetime.now(UTC)
    approval.status = "executed"
    audit(
        session,
        user,
        "ticket.reconciled",
        run.case_id,
        run.id,
        {"approval_id": str(approval.id), "ticket_id": call.response["id"]},
    )
    session.commit()
    return approval_json(approval, call)


@router.get("/runs/{run_id}/tickets")
def list_tickets(run_id: UUID, session: DB, user: Actor):
    scoped_run(session, user, run_id)
    approvals = session.scalars(
        select(ApprovalRequest)
        .where(ApprovalRequest.run_id == run_id)
        .order_by(ApprovalRequest.created_at.desc())
    ).all()
    return [
        approval_json(
            a, session.scalar(select(IntegrationCall).where(IntegrationCall.approval_id == a.id))
        )
        for a in approvals
    ]


@router.get("/approvals/{approval_id}/ticket-status")
def ticket_status(approval_id: UUID, request: Request, session: DB, user: Actor):
    settings = request.app.state.settings
    approval, _ = get_approval(session, user, approval_id)
    call = session.scalar(select(IntegrationCall).where(IntegrationCall.approval_id == approval.id))
    if call is None or call.status != "succeeded":
        raise HTTPException(409, "Ticket has not been created")
    try:
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            response = client.get(
                f"{settings.ticket_service_url}/tickets/{call.response['id']}",
                headers={"X-Service-Token": settings.ticket_service_token.get_secret_value()},
            )
            response.raise_for_status()
            result = response.json()
            if result.get("id") != call.response["id"] or result.get("run_id") != str(
                approval.run_id
            ):
                raise ValueError("Invalid ticket status response")
            return result
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Ticket service unavailable") from None
