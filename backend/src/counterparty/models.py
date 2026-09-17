"""Domain persistence. Tenant and case authorization is enforced in security.py."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from counterparty.database import Base
from counterparty.embedding_config import FINGERPRINT
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
    __table_args__ = (CheckConstraint("role IN ('analyst', 'reviewer')", name="supported_role"),)
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
    index_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    index_config: Mapped[str] = mapped_column(String(64), default=FINGERPRINT)
    index_attempts: Mapped[int] = mapped_column(Integer, default=0)
    index_owner: Mapped[str | None] = mapped_column(String(64))
    index_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    index_error: Mapped[str | None] = mapped_column(Text)


class DocumentChunk(Identity, Tenant, Base):
    __tablename__ = "document_chunks"
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessment_cases.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    location: Mapped[dict] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    embedding_model: Mapped[str | None] = mapped_column(String(100))


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
    extraction_key: Mapped[str | None] = mapped_column(String(64), index=True)
    extraction_status: Mapped[str] = mapped_column(String(20), default="ready")
    extraction_error: Mapped[str | None] = mapped_column(Text)
    requirement_embeddings: Mapped[dict | None] = mapped_column(JSONB)
    requirement_index_status: Mapped[str] = mapped_column(String(20), default="pending")
    requirement_index_error: Mapped[str | None] = mapped_column(Text)


class AnalysisRun(Identity, Tenant, Created, Base):
    __tablename__ = "analysis_runs"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_cases.id"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    policy_version_id: Mapped[UUID] = mapped_column(ForeignKey("policy_set_versions.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    input_snapshot: Mapped[dict] = mapped_column(JSONB)
    retrieval_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    assessment_progress: Mapped[dict | None] = mapped_column(JSONB)
    information_request_draft: Mapped[dict | None] = mapped_column(JSONB)
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


class WorkerModelState(Base):
    __tablename__ = "worker_model_state"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    config: Mapped[str] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
