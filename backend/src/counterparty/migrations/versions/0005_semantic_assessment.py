"""Persist extraction, approved requirement vectors and resumable assessment steps."""

from alembic import op

revision = "0005_semantic_assessment"
down_revision = "0004_learned_embeddings"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE policy_set_versions
        ADD COLUMN extraction_key VARCHAR(64),
        ADD COLUMN extraction_status VARCHAR(20) NOT NULL DEFAULT 'ready',
        ADD COLUMN extraction_error TEXT,
        ADD COLUMN requirement_embeddings JSONB,
        ADD COLUMN requirement_index_status VARCHAR(20) NOT NULL DEFAULT 'pending',
        ADD COLUMN requirement_index_error TEXT""")
    op.execute("ALTER TABLE policy_set_versions ALTER COLUMN extraction_status DROP DEFAULT")
    op.execute("ALTER TABLE policy_set_versions ALTER COLUMN requirement_index_status DROP DEFAULT")
    op.create_index(
        "ix_policy_set_versions_extraction_key", "policy_set_versions", ["extraction_key"]
    )
    op.execute("ALTER TABLE analysis_runs ADD COLUMN assessment_progress JSONB")


def downgrade():
    op.drop_column("analysis_runs", "assessment_progress")
    op.drop_index("ix_policy_set_versions_extraction_key", "policy_set_versions")
    for column in (
        "extraction_key",
        "extraction_status",
        "extraction_error",
        "requirement_embeddings",
        "requirement_index_status",
        "requirement_index_error",
    ):
        op.drop_column("policy_set_versions", column)
