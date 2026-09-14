"""Server-side identity, CSRF and object authorization; never delegated to a model."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from counterparty.models import AssessmentCase, AuditEvent, AuthSession, User

COOKIE_NAME = "counterparty_session"
WRITE_ROLES = ("analyst", "reviewer", "administrator")
REVIEW_ROLES = ("reviewer", "administrator")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session


def check_origin(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    allowed = request.app.state.settings.allowed_origins
    if origin and origin not in allowed:
        raise HTTPException(403, "Untrusted request origin")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site mutation rejected")


def current_user(request: Request, session: Annotated[Session, Depends(get_session)]) -> User:
    check_origin(request)
    token = request.cookies.get(COOKIE_NAME)
    if not token or len(token) > 200:
        raise HTTPException(401, "Authentication required")
    auth = session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    if auth is None or auth.expires_at <= datetime.now(UTC):
        raise HTTPException(401, "Session expired")
    user = session.get(User, auth.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Account unavailable")
    if not request.app.state.settings.demo_mode:
        from counterparty.bootstrap import DEMO_ACCOUNTS

        if user.email in {account["email"] for account in DEMO_ACCOUNTS}:
            raise HTTPException(403, "Demo accounts are disabled")
    return user


def require_roles(user: User, *roles: str):
    if user.role not in roles:
        raise HTTPException(403, "Insufficient role")


def get_case(session: Session, user: User, case_id: UUID) -> AssessmentCase:
    case = session.scalar(
        select(AssessmentCase).where(
            AssessmentCase.id == case_id, AssessmentCase.organization_id == user.organization_id
        )
    )
    if case is None or (user.role == "analyst" and case.owner_id != user.id):
        raise HTTPException(404, "Case not found")
    return case


def audit(session: Session, user: User, event: str, case_id=None, run_id=None, details=None):
    record = AuditEvent(
        organization_id=user.organization_id,
        actor_id=user.id,
        case_id=case_id,
        run_id=run_id,
        event=event,
        details=details or {},
    )
    session.add(record)
    return record
