from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.platform.errors import Problem, problem_response

router = APIRouter(prefix="/health", tags=["health"])


class ResponseMeta(BaseModel):
    request_id: str


class HealthData(BaseModel):
    status: Literal["ok", "ready"]


class HealthResponse(BaseModel):
    data: HealthData
    meta: ResponseMeta


def database_ready(engine: Engine) -> bool:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[2] / "alembic"))
    required_heads = set(ScriptDirectory.from_config(config).get_heads())
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            installed = set(MigrationContext.configure(connection).get_current_heads())
            extension = connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            safe_role = connection.scalar(
                text(
                    "SELECT NOT rolsuper AND NOT rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            )
            is_owner = connection.scalar(
                text(
                    "SELECT tableowner = current_user FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename = 'workspaces'"
                )
            )
            return (
                installed == required_heads
                and bool(required_heads)
                and isinstance(extension, str)
                and extension.startswith("0.8.")
                and safe_role is True
                and is_owner is False
            )
    except SQLAlchemyError:
        return False


@router.get("/live", response_model=HealthResponse)
def live(request: Request) -> HealthResponse:
    return HealthResponse(
        data=HealthData(status="ok"), meta=ResponseMeta(request_id=request.state.request_id)
    )


@router.get("/ready", response_model=HealthResponse, responses={503: {"model": Problem}})
def ready(request: Request) -> HealthResponse | JSONResponse:
    if not database_ready(request.app.state.engine):
        return problem_response(
            request,
            503,
            "dependency_unavailable",
            "The service is not ready. Try again shortly.",
            headers={"Retry-After": "5"},
        )
    return HealthResponse(
        data=HealthData(status="ready"), meta=ResponseMeta(request_id=request.state.request_id)
    )
