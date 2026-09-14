from typing import Literal

from alembic.runtime.migration import MigrationContext
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["alive", "ready", "not_ready"]


@router.get("/live", response_model=HealthStatus)
def live() -> HealthStatus:
    return HealthStatus(status="alive")


@router.get("/ready", response_model=HealthStatus, responses={503: {"model": HealthStatus}})
def ready(request: Request, response: Response) -> HealthStatus:
    try:
        with request.app.state.engine.connect() as connection:
            current = set(MigrationContext.configure(connection).get_current_heads())
        if current == request.app.state.migration_heads:
            return HealthStatus(status="ready")
    except SQLAlchemyError:
        # Database errors may contain secrets. Expose only the health state.
        pass
    response.status_code = 503
    return HealthStatus(status="not_ready")
