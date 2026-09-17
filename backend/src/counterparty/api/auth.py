"""Auth endpoints."""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, select

from counterparty.api.common import DB, Actor
from counterparty.models import AuthSession, User
from counterparty.schemas import Login
from counterparty.security import (
    COOKIE_NAME,
    WRITE_ROLES,
    audit,
    check_origin,
    token_hash,
    verify_password,
)

router = APIRouter()


def public_user(user):
    return {key: getattr(user, key) for key in ("id", "organization_id", "email", "role", "name")}


@router.get("/meta")
def meta(request: Request):
    settings = request.app.state.settings
    return {
        "version": "0.2.0",
        "demo_mode": settings.demo_mode,
        "model_mode": settings.model_mode,
        "max_upload_bytes": 10 * 1024 * 1024,
    }


@router.get("/demo/accounts")
def demo_accounts(request: Request, session: DB):
    if not request.app.state.settings.demo_mode:
        raise HTTPException(404, "Demo mode disabled")
    from counterparty.bootstrap import DEMO_ACCOUNTS, DEMO_PASSWORD

    active = set(session.scalars(select(User.email).where(User.is_active.is_(True))))
    return [
        {**account, "password": DEMO_PASSWORD}
        for account in DEMO_ACCOUNTS
        if account["email"] in active
    ]


@router.post("/auth/login")
def login(body: Login, request: Request, response: Response, session: DB):
    check_origin(request)
    user = session.scalar(select(User).where(User.email == body.email.lower()))
    # Always run a password KDF so nonexistent emails do not take a fast path.
    encoded = (
        user.password_hash
        if user
        else ("pbkdf2_sha256$600000$00000000000000000000000000000000$" + "0" * 64)
    )
    valid = verify_password(body.password, encoded)
    if user is None or not user.is_active or user.role not in WRITE_ROLES or not valid:
        raise HTTPException(401, "Invalid credentials")
    if not request.app.state.settings.demo_mode:
        from counterparty.bootstrap import DEMO_EMAILS

        if user.email in DEMO_EMAILS:
            raise HTTPException(403, "Demo accounts are disabled")
    token = secrets.token_urlsafe(32)
    old = request.cookies.get(COOKIE_NAME)
    if old:
        session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(old)))
    session.execute(delete(AuthSession).where(AuthSession.expires_at <= datetime.now(UTC)))
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=datetime.now(UTC) + timedelta(hours=12),
        )
    )
    audit(session, user, "auth.login")
    session.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        secure=request.app.state.settings.cookie_secure,
        max_age=43200,
        path="/",
    )
    return public_user(user)


@router.get("/auth/me")
def me(user: Actor):
    return public_user(user)


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: Actor, session: DB):
    session.execute(
        delete(AuthSession).where(
            AuthSession.token_hash == token_hash(request.cookies.get(COOKIE_NAME, ""))
        )
    )
    audit(session, user, "auth.logout")
    session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
