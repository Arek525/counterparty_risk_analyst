"""Create versioned domain records, server sessions and pgvector embeddings."""

import pgvector.sqlalchemy.vector
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_domain"
down_revision = "0001_organizations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_users_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)
    op.create_table(
        "assessment_cases",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("counterparty_name", sa.String(length=200), nullable=False),
        sa.Column("relationship", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_assessment_cases_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_assessment_cases_owner_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_cases")),
    )
    op.create_index(
        op.f("ix_assessment_cases_organization_id"),
        "assessment_cases",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_table(
        "policy_set_versions",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("document_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], name=op.f("fk_policy_set_versions_approved_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_policy_set_versions_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_policy_set_versions_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_set_versions")),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            "version",
            name=op.f("uq_policy_set_versions_organization_id"),
        ),
    )
    op.create_index(
        op.f("ix_policy_set_versions_organization_id"),
        "policy_set_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "analysis_runs",
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retrieval_variant", sa.String(length=30), nullable=False),
        sa.Column("model_mode", sa.String(length=30), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["assessment_cases.id"],
            name=op.f("fk_analysis_runs_case_id_assessment_cases"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_analysis_runs_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_analysis_runs_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["policy_set_versions.id"],
            name=op.f("fk_analysis_runs_policy_version_id_policy_set_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    op.create_index(op.f("ix_analysis_runs_case_id"), "analysis_runs", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_analysis_runs_organization_id"), "analysis_runs", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_analysis_runs_status"), "analysis_runs", ["status"], unique=False)
    op.create_table(
        "documents",
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["assessment_cases.id"], name=op.f("fk_documents_case_id_assessment_cases")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_documents_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name=op.f("fk_documents_uploaded_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index(op.f("ix_documents_case_id"), "documents", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_documents_organization_id"), "documents", ["organization_id"], unique=False
    )
    op.create_table(
        "approval_requests",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("arguments_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], name=op.f("fk_approval_requests_approved_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_approval_requests_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], name=op.f("fk_approval_requests_requested_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["analysis_runs.id"], name=op.f("fk_approval_requests_run_id_analysis_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_requests")),
    )
    op.create_index(
        op.f("ix_approval_requests_organization_id"),
        "approval_requests",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_requests_run_id"), "approval_requests", ["run_id"], unique=False
    )
    op.create_table(
        "audit_events",
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("event", sa.String(length=100), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_audit_events_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["assessment_cases.id"],
            name=op.f("fk_audit_events_case_id_assessment_cases"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_audit_events_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["analysis_runs.id"], name=op.f("fk_audit_events_run_id_analysis_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_case_id"), "audit_events", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_audit_events_organization_id"), "audit_events", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_audit_events_run_id"), "audit_events", ["run_id"], unique=False)
    op.create_table(
        "decisions",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_decisions_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_decisions_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["analysis_runs.id"], name=op.f("fk_decisions_run_id_analysis_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decisions")),
        sa.UniqueConstraint("run_id", name=op.f("uq_decisions_run_id")),
    )
    op.create_index(
        op.f("ix_decisions_organization_id"), "decisions", ["organization_id"], unique=False
    )
    op.create_table(
        "document_chunks",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=128), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["assessment_cases.id"],
            name=op.f("fk_document_chunks_case_id_assessment_cases"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_document_chunks_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
    )
    op.create_index(
        op.f("ix_document_chunks_case_id"), "document_chunks", ["case_id"], unique=False
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_document_chunks_organization_id"),
        "document_chunks",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "integration_calls",
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["approval_requests.id"],
            name=op.f("fk_integration_calls_approval_id_approval_requests"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_integration_calls_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_calls")),
        sa.UniqueConstraint("approval_id", name=op.f("uq_integration_calls_approval_id")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_integration_calls_idempotency_key")),
    )
    op.create_index(
        op.f("ix_integration_calls_organization_id"),
        "integration_calls",
        ["organization_id"],
        unique=False,
    )


def downgrade():
    op.drop_table("integration_calls")
    op.drop_table("document_chunks")
    op.drop_table("decisions")
    op.drop_table("audit_events")
    op.drop_table("approval_requests")
    op.drop_table("documents")
    op.drop_table("analysis_runs")
    op.drop_table("policy_set_versions")
    op.drop_table("auth_sessions")
    op.drop_table("assessment_cases")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
