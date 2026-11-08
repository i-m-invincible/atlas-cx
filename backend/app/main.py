import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.modules.customers.router import router as customers_router
from app.modules.identity.router import router as identity_router
from app.modules.workspace.router import router as workspace_router
from app.platform.config import get_settings
from app.platform.database import build_engine
from app.platform.errors import FieldError, problem_response
from app.platform.health import router as health_router
from app.platform.protocol import Fault

logger = logging.getLogger("atlas.requests")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    yield
    application.state.engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    application = FastAPI(
        title="Atlas CX API",
        version="0.1.0",
        description="Atlas CX identity, workspace, and customer core API.",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
    )
    application.state.engine = build_engine(settings.database_url.get_secret_value())

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            response = problem_response(
                request, 500, "internal_error", "The request could not be completed."
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        logger.info(
            json.dumps(
                {
                    "request_id": request.state.request_id,
                    "route": getattr(route, "path", "unmatched"),
                    "status": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                }
            )
        )
        return response

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> Response:
        codes = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
        }
        return problem_response(
            request,
            exc.status_code,
            codes.get(exc.status_code, "request_failed"),
            str(exc.detail),
            headers=dict(exc.headers) if exc.headers else None,
        )

    @application.exception_handler(Fault)
    async def domain_error(request: Request, exc: Fault) -> Response:
        return problem_response(request, exc.status, exc.code, exc.detail, headers=exc.headers)

    @application.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError) -> Response:
        return problem_response(
            request,
            409,
            "record_conflict",
            "These details conflict with an existing record in this workspace.",
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> Response:
        return problem_response(
            request, 503, "dependency_unavailable", "The service is unavailable. Try again shortly."
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> Response:
        fields = [
            FieldError(
                path=".".join(str(part) for part in error["loc"]),
                code=error["type"],
                message="This value is invalid.",
            )
            for error in exc.errors()
        ]
        return problem_response(
            request, 422, "validation_error", "Review the highlighted fields.", fields
        )

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(identity_router, prefix="/api/v1")
    application.include_router(customers_router, prefix="/api/v1")
    application.include_router(workspace_router, prefix="/api/v1")
    return application


app = create_app()
