"""Remove obsolete workflow storage; business reports and progress remain authoritative."""

from alembic import op

revision = "0008_remove_checkpoints"
down_revision = "0007_information_requests"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "checkpoint_migrations"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("""
        UPDATE analysis_runs
        SET report = (report - 'workflow_error') || '{"workflow_complete": true}'::jsonb,
            status = 'completed', error = NULL,
            lease_owner = NULL, lease_expires_at = NULL
        WHERE report IS NOT NULL
          AND EXISTS (SELECT 1 FROM decisions WHERE decisions.run_id = analysis_runs.id)
    """)


def downgrade():
    # Obsolete execution checkpoints cannot be reconstructed. Business data is retained.
    pass
