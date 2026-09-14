"""Local REST ticketing simulator with durable idempotency receipts."""

import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from counterparty.config import Settings
from counterparty.database import Base, create_engine_for_settings


class TicketReceipt(Base):
    __tablename__ = "demo_tickets"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class TicketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    organization_id: UUID
    run_id: UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def receipt_json(row):
    return {
        "id": str(row.id),
        "status": row.status,
        "title": row.payload["title"],
        "body": row.payload["body"],
        "run_id": row.payload["run_id"],
        "organization_id": row.payload["organization_id"],
        "created_at": row.created_at.isoformat(),
        "service": "local-demo-ticketing",
    }


def create_receipt(engine, key: str, payload: dict) -> dict:
    digest = payload_hash(payload)
    with Session(engine) as session, session.begin():
        session.execute(
            insert(TicketReceipt)
            .values(idempotency_key=key, payload_hash=digest, payload=payload)
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        row = session.scalar(select(TicketReceipt).where(TicketReceipt.idempotency_key == key))
        if row.payload_hash != digest:
            raise HTTPException(409, "Idempotency key already used for different arguments")
        return receipt_json(row)


def authenticate(request: Request, x_service_token: str = Header(default="")):
    expected = request.app.state.settings.ticket_service_token.get_secret_value()
    if not hmac.compare_digest(x_service_token, expected):
        raise HTTPException(401, "Service authentication required")


def create_app():
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings
        app.state.engine = create_engine_for_settings(settings)
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(title="Local demo ticketing", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "alive"}

    @app.post("/tickets", dependencies=[Depends(authenticate)])
    def create(
        payload: TicketPayload, request: Request, idempotency_key: Annotated[UUID, Header()]
    ):
        return create_receipt(
            request.app.state.engine, str(idempotency_key), payload.model_dump(mode="json")
        )

    @app.get("/tickets/by-key/{key}", dependencies=[Depends(authenticate)])
    def read_by_key(key: UUID, request: Request):
        with Session(request.app.state.engine) as session:
            row = session.scalar(
                select(TicketReceipt).where(TicketReceipt.idempotency_key == str(key))
            )
            if row is None:
                raise HTTPException(404, "Ticket not found")
            return receipt_json(row)

    @app.get("/tickets/{ticket_id}", dependencies=[Depends(authenticate)])
    def read(ticket_id: UUID, request: Request):
        with Session(request.app.state.engine) as session:
            row = session.get(TicketReceipt, ticket_id)
            if row is None:
                raise HTTPException(404, "Ticket not found")
            return receipt_json(row)

    return app
