"""Domain persistence. Tenant and case authorization is enforced in security.py."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from counterparty.database import Base
from counterparty.organizations import Organization as Organization


def now():
    return datetime.now(UTC)


class Identity:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Tenant:
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)


class Created:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Identity, Tenant, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthSession(Identity, Created, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AssessmentCase(Identity, Tenant, Created, Base):
    __tablename__ = "assessment_cases"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    counterparty_name: Mapped[str] = mapped_column(String(200))
    relationship: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Document(Identity, Tenant, Created, Base):
    __tablename__ = "documents"
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessment_cases.id"), index=True)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(255))
    evidence_type: Mapped[str] = mapped_column(String(30), default="declaration")
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(100))


class DocumentChunk(Identity, Tenant, Base):
    __tablename__ = "document_chunks"
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessment_cases.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    location: Mapped[dict] = mapped_column(JSONB)
    embedding: Mapped[list[float]] = mapped_column(Vector(128))
    embedding_model: Mapped[str] = mapped_column(String(100), default="demo-hash-v1")


class PolicySetVersion(Identity, Tenant, Created, Base):
    __tablename__ = "policy_set_versions"
    __table_args__ = (UniqueConstraint("organization_id", "name", "version"),)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    document_ids: Mapped[list] = mapped_column(JSONB)
    requirements: Mapped[list] = mapped_column(JSONB)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisRun(Identity, Tenant, Created, Base):
    __tablename__ = "analysis_runs"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_cases.id"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    policy_version_id: Mapped[UUID] = mapped_column(ForeignKey("policy_set_versions.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    input_snapshot: Mapped[dict] = mapped_column(JSONB)
    report: Mapped[dict | None] = mapped_column(JSONB)
    retrieval_variant: Mapped[str] = mapped_column(String(30), default="hybrid")
    model_mode: Mapped[str] = mapped_column(String(30), default="demo")
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Decision(Identity, Tenant, Created, Base):
    __tablename__ = "decisions"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id"), unique=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))
    rationale: Mapped[str] = mapped_column(Text)


class AuditEvent(Identity, Tenant, Created, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessment_cases.id"), index=True)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    event: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class ApprovalRequest(Identity, Tenant, Created, Base):
    __tablename__ = "approval_requests"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50), default="create_ticket")
    arguments: Mapped[dict] = mapped_column(JSONB)
    arguments_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntegrationCall(Identity, Tenant, Created, Base):
    __tablename__ = "integration_calls"
    approval_id: Mapped[UUID] = mapped_column(ForeignKey("approval_requests.id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    request: Mapped[dict] = mapped_column(JSONB)
    response: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
