from contextlib import asynccontextmanager
from pathlib import Path

from alembic.script import ScriptDirectory
from fastapi import FastAPI

from counterparty.config import Settings
from counterparty.database import create_engine_for_settings
from counterparty.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    migration_heads = set(ScriptDirectory(str(Path(__file__).with_name("migrations"))).get_heads())
    if not migration_heads:
        raise RuntimeError("The application must ship with database migrations")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine_for_settings(settings)
        app.state.engine = engine
        app.state.migration_heads = migration_heads
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Counterparty Risk Analyst", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    return app
