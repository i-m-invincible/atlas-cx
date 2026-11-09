from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field
from sqlalchemy import select

from app.modules.cases.schemas import ConfigView, Definition
from app.modules.workspace import case_config_service as service
from app.modules.workspace.case_config_models import CaseConfig
from app.modules.workspace.case_presets import CasePreset, starter_presets
from app.platform.auth import UnitOfWork, require_role, staff_uow
from app.platform.protocol import Envelope, Fault, Input, Meta, read_cursor, result, sign_cursor

router = APIRouter(tags=["case configuration"])
Staff = Annotated[UnitOfWork, Depends(staff_uow, scope="function")]


class Filters(Input):
    status: Literal["draft", "published"] | None = None
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)


@router.get("/case-presets")
def presets(request: Request, uow: Staff) -> Envelope[list[CasePreset]]:
    require_role(uow.scope, "admin")
    return result(request, starter_presets())


@router.get("/case-configs")
def configs(
    request: Request, filters: Annotated[Filters, Query()], uow: Staff
) -> Envelope[list[ConfigView]]:
    query = select(CaseConfig)
    if uow.scope.role != "admin":
        query = query.where(CaseConfig.status == "published")
    if filters.status:
        query = query.where(CaseConfig.status == filters.status)
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "resource": "case-configs",
        "status": filters.status,
        "admin": uow.scope.role == "admin",
    }
    if filters.cursor:
        try:
            (number,) = read_cursor(filters.cursor, binding)
            query = query.where(CaseConfig.number < int(number))
        except ValueError:
            raise Fault(400, "invalid_cursor", "Return to the first configuration page.") from None
    rows = list(
        uow.session.scalars(query.order_by(CaseConfig.number.desc()).limit(filters.limit + 1))
    )
    next_cursor = (
        sign_cursor(binding, [str(rows[filters.limit - 1].number)])
        if len(rows) > filters.limit
        else None
    )
    return Envelope(
        data=[service.view(row) for row in rows[: filters.limit]],
        meta=Meta(
            request_id=request.state.request_id,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
        ),
    )


@router.get("/case-configs/{identifier}")
def detail(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[ConfigView]:
    return result(request, service.view(service.get(uow, identifier)), response)


@router.post("/case-configs", status_code=201)
def create(
    payload: Definition, request: Request, response: Response, uow: Staff
) -> Envelope[ConfigView]:
    row = service.save(uow, payload, request)
    response.headers["Location"] = f"/api/v1/case-configs/{row.id}"
    return result(request, service.view(row), response)


@router.patch("/case-configs/{identifier}")
def edit(
    identifier: UUID, payload: Definition, request: Request, response: Response, uow: Staff
) -> Envelope[ConfigView]:
    return result(request, service.view(service.save(uow, payload, request, identifier)), response)


@router.post("/case-configs/{identifier}/publish")
def publish(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[ConfigView]:
    return result(request, service.view(service.publish(uow, identifier, request)), response)
