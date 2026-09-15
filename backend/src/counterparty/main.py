from contextlib import asynccontextmanager
from pathlib import Path

from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from counterparty.analysis.adapters import ModelError
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
        app.state.settings = settings
        app.state.migration_heads = migration_heads
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Counterparty Risk Analyst", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(ModelError)
    async def model_error_handler(request: Request, exc: ModelError):
        # Adapter errors contain curated operational messages, never provider bodies/keys.
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    app.include_router(health_router)
    from counterparty.integrations import router as integrations_router
    from counterparty.routes import router

    app.include_router(router)
    app.include_router(integrations_router)
    from counterparty.deletion import router as deletion_router

    app.include_router(deletion_router)
    return app
