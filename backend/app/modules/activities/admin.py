import secrets
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, tuple_

from app.modules.activities.models import EventDefinition
from app.modules.activities.schemas import (
    DefinitionCreate,
    DefinitionPatch,
    DefinitionView,
    PageFilters,
    PropertyRule,
)
from app.modules.cases.router import Staff, listing
from app.modules.identity.security import digest
from app.modules.workspace.credential_models import ApiCredential
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role
from app.platform.protocol import (
    Envelope,
    Fault,
    Input,
    match_version,
    missing,
    now,
    read_cursor,
    result,
    sign_cursor,
)

router = APIRouter(tags=["event tracking"])


class CredentialCreate(Input):
    name: str = Field(min_length=1, max_length=120)


class CredentialView(BaseModel):
    id: UUID
    name: str
    version: int
    token_prefix: str
    scope: Literal["events:write"]
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class CredentialIssued(CredentialView):
    secret: str


def definition_view(row: EventDefinition) -> DefinitionView:
    return DefinitionView(
        id=row.id,
        key=row.key,
        label=row.label,
        allowed_properties={
            key: PropertyRule.model_validate(rule)
            for key, rule in row.allowed_properties_json.items()
        },
        counts_as_activity=row.counts_as_activity,
        enabled=row.enabled,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def credential_view(row: ApiCredential) -> CredentialView:
    return CredentialView(
        id=row.id,
        name=row.name,
        version=row.version,
        token_prefix=row.token_prefix,
        scope="events:write",
        revoked_at=row.revoked_at,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
    )


def page[T: EventDefinition | ApiCredential](
    uow: UnitOfWork,
    model: type[T],
    filters: PageFilters,
) -> tuple[list[T], str | None]:
    binding = {"workspace": str(uow.scope.workspace_id), "resource": model.__tablename__}
    query = select(model)
    if filters.cursor:
        try:
            created, identifier = read_cursor(filters.cursor, binding)
            query = query.where(
                tuple_(model.created_at, model.id)
                < (datetime.fromisoformat(created), UUID(identifier))
            )
        except ValueError:
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    rows = list(
        uow.session.scalars(
            query.order_by(model.created_at.desc(), model.id.desc()).limit(filters.limit + 1)
        )
    )
    last = rows[filters.limit - 1] if len(rows) > filters.limit else None
    return rows[: filters.limit], sign_cursor(
        binding, [last.created_at.isoformat(), str(last.id)]
    ) if last else None


def get[T: EventDefinition | ApiCredential](
    uow: UnitOfWork,
    model: type[T],
    identifier: UUID,
    lock: bool = False,
) -> T:
    row = uow.session.get(model, identifier, with_for_update=lock)
    if row is None:
        raise missing()
    return row


def audit(
    uow: UnitOfWork,
    request: Request,
    action: str,
    row: EventDefinition | ApiCredential,
    fields: list[str],
) -> None:
    record_audit(
        uow.session,
        row.workspace_id,
        uow.scope.user_id,
        action,
        "event_definition" if isinstance(row, EventDefinition) else "api_credential",
        row.id,
        fields,
        request.state.request_id,
    )


@router.get("/event-definitions")
def definitions(
    request: Request, filters: Annotated[PageFilters, Query()], uow: Staff
) -> Envelope[list[DefinitionView]]:
    rows, cursor = page(uow, EventDefinition, filters)
    return listing(request, [definition_view(row) for row in rows], cursor)


@router.get("/event-definitions/{identifier}")
def definition(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[DefinitionView]:
    return result(request, definition_view(get(uow, EventDefinition, identifier)), response)


@router.post("/event-definitions", status_code=201)
def create_definition(
    payload: DefinitionCreate, request: Request, response: Response, uow: Staff
) -> Envelope[DefinitionView]:
    require_role(uow.scope, "admin")
    values = payload.model_dump(mode="json")
    values["allowed_properties_json"] = values.pop("allowed_properties")
    row = EventDefinition(workspace_id=uow.scope.workspace_id, **values)
    uow.session.add(row)
    uow.session.flush()
    audit(uow, request, "event_definition.created", row, list(payload.model_fields_set))
    response.headers["Location"] = f"/api/v1/event-definitions/{row.id}"
    return result(request, definition_view(row), response)


@router.patch("/event-definitions/{identifier}")
def update_definition(
    identifier: UUID, payload: DefinitionPatch, request: Request, response: Response, uow: Staff
) -> Envelope[DefinitionView]:
    require_role(uow.scope, "admin")
    row = get(uow, EventDefinition, identifier, True)
    match_version(request, row.version)
    for key, value in payload.model_dump(mode="json", exclude_unset=True).items():
        setattr(row, "allowed_properties_json" if key == "allowed_properties" else key, value)
    row.version += 1
    row.updated_at = now()
    audit(uow, request, "event_definition.updated", row, list(payload.model_fields_set))
    uow.session.flush()
    return result(request, definition_view(row), response)


@router.get("/api-credentials")
def credentials(
    request: Request, filters: Annotated[PageFilters, Query()], uow: Staff
) -> Envelope[list[CredentialView]]:
    require_role(uow.scope, "admin")
    rows, cursor = page(uow, ApiCredential, filters)
    return listing(request, [credential_view(row) for row in rows], cursor)


@router.get("/api-credentials/{identifier}")
def credential(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[CredentialView]:
    require_role(uow.scope, "admin")
    return result(request, credential_view(get(uow, ApiCredential, identifier)), response)


@router.post("/api-credentials", status_code=201)
def issue(
    payload: CredentialCreate, request: Request, response: Response, uow: Staff
) -> Envelope[CredentialIssued]:
    require_role(uow.scope, "admin")
    token = "atlas_ev_" + secrets.token_urlsafe(32)
    row = ApiCredential(
        workspace_id=uow.scope.workspace_id,
        name=payload.name,
        token_hash=digest(token),
        token_prefix=token[:17],
    )
    uow.session.add(row)
    uow.session.flush()
    audit(uow, request, "api_credential.created", row, ["name", "scope"])
    response.headers["Location"] = f"/api/v1/api-credentials/{row.id}"
    return result(
        request, CredentialIssued(**credential_view(row).model_dump(), secret=token), response
    )


@router.post("/api-credentials/{identifier}/revoke")
def revoke(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[CredentialView]:
    require_role(uow.scope, "admin")
    row = get(uow, ApiCredential, identifier, True)
    match_version(request, row.version)
    if row.revoked_at is None:
        row.revoked_at = row.updated_at = now()
        row.version += 1
        audit(uow, request, "api_credential.revoked", row, ["revoked_at"])
    uow.session.flush()
    return result(request, credential_view(row), response)
