from datetime import datetime
from typing import Annotated, TypeVar, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import Select, literal, select, tuple_
from sqlalchemy.orm import InstrumentedAttribute

from app.modules.customers.schemas import ContactView
from app.modules.identity.models import Membership
from app.modules.workspace import service
from app.modules.workspace.models import Workspace
from app.modules.workspace.schemas import (
    AccessPatch,
    AuditView,
    MemberCreate,
    MemberFilters,
    MemberPatch,
    MemberSetupView,
    MemberView,
    PageFilters,
    PortalSetupView,
    TeamCreate,
    TeamPatch,
    TeamView,
    WorkspacePatch,
    WorkspaceView,
)
from app.modules.workspace.team_models import Team
from app.platform.audit import AuditEvent
from app.platform.auth import UnitOfWork, require_role, staff_uow
from app.platform.protocol import Envelope, Fault, Meta, missing, read_cursor, result, sign_cursor

router = APIRouter(tags=["workspace"])
Uow = Annotated[UnitOfWork, Depends(staff_uow, scope="function")]
T = TypeVar("T", bound=Membership | Team)


def page[T: Membership | Team](
    uow: UnitOfWork,
    query: Select[tuple[T]],
    id_column: InstrumentedAttribute[UUID],
    created_column: InstrumentedAttribute[datetime],
    filters: PageFilters,
    resource: str,
) -> tuple[list[T], str | None]:
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "resource": resource,
        **filters.model_dump(mode="json", exclude={"limit", "cursor"}),
    }
    if filters.cursor:
        try:
            stamp, identifier = read_cursor(filters.cursor, binding)
            query = query.where(
                tuple_(created_column, id_column)
                < tuple_(literal(datetime.fromisoformat(stamp)), literal(UUID(identifier)))
            )
        except (ValueError, TypeError):
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    rows = list(
        uow.session.scalars(
            query.order_by(created_column.desc(), id_column.desc()).limit(filters.limit + 1)
        )
    )
    more = len(rows) > filters.limit
    rows = rows[: filters.limit]
    last = rows[-1] if more else None
    cursor = sign_cursor(binding, [last.created_at.isoformat(), str(last.id)]) if last else None
    return rows, cursor


@router.get("/workspace", response_model=Envelope[WorkspaceView])
def get_workspace(request: Request, response: Response, uow: Uow) -> Envelope[WorkspaceView]:
    row = uow.session.get(Workspace, uow.scope.workspace_id)
    assert row
    return result(request, service.workspace_view(row), response)


@router.patch("/workspace", response_model=Envelope[WorkspaceView])
def patch_workspace(
    payload: WorkspacePatch, request: Request, response: Response, uow: Uow
) -> Envelope[WorkspaceView]:
    return result(request, service.update_workspace(uow, payload, request), response)


@router.get("/members", response_model=Envelope[list[MemberView]])
def members(
    request: Request, filters: Annotated[MemberFilters, Query()], uow: Uow
) -> Envelope[list[MemberView]]:
    query = select(Membership)
    if filters.active is not None:
        query = query.where(Membership.active == filters.active)
    if filters.role:
        query = query.where(Membership.role == filters.role)
    rows, cursor = page(uow, query, Membership.id, Membership.created_at, filters, "members")
    return Envelope(
        data=[service.member_view(uow, row) for row in rows],
        meta=Meta(
            request_id=request.state.request_id, next_cursor=cursor, has_more=cursor is not None
        ),
    )


@router.get("/members/{identifier}", response_model=Envelope[MemberView])
def member(
    identifier: UUID, request: Request, response: Response, uow: Uow
) -> Envelope[MemberView]:
    row = uow.session.get(Membership, identifier)
    if not row:
        raise missing()
    return result(request, service.member_view(uow, row), response)


@router.post("/members", status_code=201, response_model=Envelope[MemberSetupView])
def create_member(
    payload: MemberCreate, request: Request, response: Response, uow: Uow
) -> Envelope[MemberSetupView]:
    data = service.create_member(uow, payload, request)
    response.headers["Location"] = f"/api/v1/members/{data.member.id}"
    response.headers["ETag"] = f'"{data.member.version}"'
    return result(request, data)


@router.patch("/members/{identifier}", response_model=Envelope[MemberView])
def patch_member(
    identifier: UUID, payload: MemberPatch, request: Request, response: Response, uow: Uow
) -> Envelope[MemberView]:
    return result(request, service.update_member(uow, identifier, payload, request), response)


@router.post("/contacts/{identifier}/portal-access", response_model=Envelope[PortalSetupView])
def create_portal_setup(
    identifier: UUID, request: Request, response: Response, uow: Uow
) -> Envelope[PortalSetupView]:
    data = service.portal_setup(uow, identifier, request)
    response.headers["ETag"] = f'"{data.contact.version}"'
    return result(request, data)


@router.patch("/contacts/{identifier}/portal-access", response_model=Envelope[ContactView])
def patch_portal_access(
    identifier: UUID, payload: AccessPatch, request: Request, response: Response, uow: Uow
) -> Envelope[ContactView]:
    return result(
        request,
        cast(ContactView, service.portal_access(uow, identifier, payload.active, request)),
        response,
    )


@router.get("/teams", response_model=Envelope[list[TeamView]])
def teams(
    request: Request, filters: Annotated[PageFilters, Query()], uow: Uow
) -> Envelope[list[TeamView]]:
    rows, cursor = page(uow, select(Team), Team.id, Team.created_at, filters, "teams")
    return Envelope(
        data=[service.team_view(uow, row) for row in rows],
        meta=Meta(
            request_id=request.state.request_id, next_cursor=cursor, has_more=cursor is not None
        ),
    )


@router.get("/teams/{identifier}", response_model=Envelope[TeamView])
def get_team(
    identifier: UUID, request: Request, response: Response, uow: Uow
) -> Envelope[TeamView]:
    row = uow.session.get(Team, identifier)
    if not row:
        raise missing()
    return result(request, service.team_view(uow, row), response)


@router.post("/teams", status_code=201, response_model=Envelope[TeamView])
def create_team(
    payload: TeamCreate, request: Request, response: Response, uow: Uow
) -> Envelope[TeamView]:
    data = service.save_team(uow, payload, request)
    response.headers["Location"] = f"/api/v1/teams/{data.id}"
    return result(request, data, response)


@router.patch("/teams/{identifier}", response_model=Envelope[TeamView])
def patch_team(
    identifier: UUID, payload: TeamPatch, request: Request, response: Response, uow: Uow
) -> Envelope[TeamView]:
    return result(request, service.save_team(uow, payload, request, identifier), response)


@router.get("/audit", response_model=Envelope[list[AuditView]])
def audit(
    request: Request, filters: Annotated[PageFilters, Query()], uow: Uow
) -> Envelope[list[AuditView]]:
    require_role(uow.scope, "admin", "manager")
    binding = {"workspace": str(uow.scope.workspace_id), "resource": "audit"}
    query = select(AuditEvent)
    if filters.cursor:
        try:
            (value,) = read_cursor(filters.cursor, binding)
            query = query.where(AuditEvent.sequence < int(value))
        except (ValueError, TypeError):
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    rows = list(
        uow.session.scalars(query.order_by(AuditEvent.sequence.desc()).limit(filters.limit + 1))
    )
    more = len(rows) > filters.limit
    rows = rows[: filters.limit]
    cursor = sign_cursor(binding, [str(rows[-1].sequence)]) if more else None
    data = [
        AuditView(**{field: getattr(row, field) for field in AuditView.model_fields})
        for row in rows
    ]
    return Envelope(
        data=data, meta=Meta(request_id=request.state.request_id, has_more=more, next_cursor=cursor)
    )
