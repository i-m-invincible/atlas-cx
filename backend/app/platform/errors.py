from http import HTTPStatus
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class FieldError(BaseModel):
    path: str
    code: str
    message: str


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    instance: str
    request_id: str
    field_errors: list[FieldError] | None = None


def problem_response(
    request: Request,
    status: int,
    code: str,
    detail: str,
    field_errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = Problem(
        title=HTTPStatus(status).phrase,
        status=status,
        code=code,
        detail=detail,
        instance=request.url.path,
        request_id=request.state.request_id,
        field_errors=field_errors,
    )
    content: dict[str, Any] = payload.model_dump(exclude_none=True)
    return JSONResponse(
        content, status_code=status, media_type="application/problem+json", headers=headers
    )
