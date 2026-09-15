"""Replace demo vectors without changing source chunks or historical reports."""

from alembic import op

revision = "0004_learned_embeddings"
down_revision = "0003_demo_tickets"
branch_labels = None
depends_on = None


def upgrade():
    # Literal frozen fingerprint: never import evolving application config in migrations.
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding DROP NOT NULL")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(384) USING NULL")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding_model DROP NOT NULL")
    op.execute("UPDATE document_chunks SET embedding_model = NULL")
    op.execute("ALTER TABLE analysis_runs ADD COLUMN retrieval_snapshot JSONB")
    op.execute("""ALTER TABLE documents
        ADD COLUMN index_status VARCHAR(20) NOT NULL DEFAULT 'pending',
        ADD COLUMN index_config VARCHAR(64) NOT NULL
            DEFAULT '800ce15e8c69d74e89ab87bc2965eff571505bbdaf79c8570a8cdacbb60597e3',
        ADD COLUMN index_attempts INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN index_owner VARCHAR(64),
        ADD COLUMN index_lease_expires_at TIMESTAMPTZ,
        ADD COLUMN indexed_at TIMESTAMPTZ,
        ADD COLUMN index_error TEXT""")
    for column in ("index_status", "index_config", "index_attempts"):
        op.execute(f"ALTER TABLE documents ALTER COLUMN {column} DROP DEFAULT")
    op.create_index("ix_documents_index_status", "documents", ["index_status"])
    op.execute("""CREATE TABLE worker_model_state (
        id VARCHAR(50) PRIMARY KEY, status VARCHAR(20) NOT NULL,
        config VARCHAR(64) NOT NULL, error TEXT, heartbeat_at TIMESTAMPTZ NOT NULL)""")
    op.execute("""CREATE FUNCTION protect_analysis_snapshots() RETURNS trigger AS $$
        BEGIN
          IF NEW.input_snapshot IS DISTINCT FROM OLD.input_snapshot THEN
            RAISE EXCEPTION 'Analysis input snapshot is immutable';
          END IF;
          IF OLD.retrieval_snapshot IS NOT NULL AND
             NEW.retrieval_snapshot IS DISTINCT FROM OLD.retrieval_snapshot THEN
            RAISE EXCEPTION 'Retrieval snapshot is write-once';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER analysis_snapshots_immutable BEFORE UPDATE ON analysis_runs
        FOR EACH ROW EXECUTE FUNCTION protect_analysis_snapshots()""")


def downgrade():
    op.execute("DROP TRIGGER analysis_snapshots_immutable ON analysis_runs")
    op.execute("DROP FUNCTION protect_analysis_snapshots()")
    op.drop_table("worker_model_state")
    op.drop_column("analysis_runs", "retrieval_snapshot")
    op.drop_index("ix_documents_index_status", "documents")
    for column in (
        "index_status",
        "index_config",
        "index_attempts",
        "index_owner",
        "index_lease_expires_at",
        "indexed_at",
        "index_error",
    ):
        op.drop_column("documents", column)
    # Learned vectors cannot be converted back into historical hash vectors.
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(128) USING NULL")
