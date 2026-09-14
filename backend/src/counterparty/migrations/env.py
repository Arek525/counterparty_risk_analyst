from alembic import context

from counterparty import models  # noqa: F401 -- register domain metadata
from counterparty.config import Settings
from counterparty.database import Base, create_engine_for_settings
from counterparty.organizations import Organization  # noqa: F401 -- register model metadata

CHECKPOINT_TABLES = {
    "checkpoint_migrations",
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "demo_tickets",
}


def include_object(obj, name, type_, reflected, compare_to):
    return not (type_ == "table" and name in CHECKPOINT_TABLES)


config = context.config
override_url = config.attributes.get("database_url")
settings = Settings(database_url=override_url) if override_url else Settings()

if context.is_offline_mode():
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine_for_settings(settings)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                include_object=include_object,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
