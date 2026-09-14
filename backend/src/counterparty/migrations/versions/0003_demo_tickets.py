"""Durable receipts for the separate local REST ticketing simulator."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_demo_tickets"
down_revision = "0002_domain"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "demo_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_demo_tickets"),
        sa.UniqueConstraint("idempotency_key", name="uq_demo_tickets_idempotency_key"),
    )


def downgrade():
    op.drop_table("demo_tickets")
