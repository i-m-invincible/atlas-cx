from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.modules.activities import admin_service as service
from app.modules.activities.admin_service import CredentialCreate, CredentialIssued, CredentialView
from app.modules.activities.models import EventDefinition
from app.modules.activities.schemas import (
    DefinitionCreate,
    DefinitionPatch,
    DefinitionView,
    PageFilters,
)
from app.modules.cases.router import Staff, listing
from app.modules.workspace.credential_models import ApiCredential
from app.platform.protocol import Envelope, result

router = APIRouter(tags=["event tracking"])


@router.get("/event-definitions")
def definitions(
    request: Request, filters: Annotated[PageFilters, Query()], uow: Staff
) -> Envelope[list[DefinitionView]]:
    rows, cursor = service.page(uow, EventDefinition, filters)
    return listing(request, [service.definition_view(row) for row in rows], cursor)


@router.get("/event-definitions/{identifier}")
def definition(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[DefinitionView]:
    return result(
        request, service.definition_view(service.get(uow, EventDefinition, identifier)), response
    )


@router.post("/event-definitions", status_code=201)
def create_definition(
    payload: DefinitionCreate, request: Request, response: Response, uow: Staff
) -> Envelope[DefinitionView]:
    row = service.create_definition(payload, request, uow)
    response.headers["Location"] = f"/api/v1/event-definitions/{row.id}"
    return result(request, row, response)


@router.patch("/event-definitions/{identifier}")
def update_definition(
    identifier: UUID, payload: DefinitionPatch, request: Request, response: Response, uow: Staff
) -> Envelope[DefinitionView]:
    return result(request, service.update_definition(identifier, payload, request, uow), response)


@router.get("/api-credentials")
def credentials(
    request: Request, filters: Annotated[PageFilters, Query()], uow: Staff
) -> Envelope[list[CredentialView]]:
    rows, cursor = service.page(uow, ApiCredential, filters)
    return listing(request, [service.credential_view(row) for row in rows], cursor)


@router.get("/api-credentials/{identifier}")
def credential(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[CredentialView]:
    return result(
        request, service.credential_view(service.get(uow, ApiCredential, identifier)), response
    )


@router.post("/api-credentials", status_code=201)
def issue(
    payload: CredentialCreate, request: Request, response: Response, uow: Staff
) -> Envelope[CredentialIssued]:
    key = service.issue(payload, request, uow)
    response.headers["Location"] = f"/api/v1/api-credentials/{key.id}"
    return result(request, key, response)


@router.post("/api-credentials/{identifier}/revoke")
def revoke(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[CredentialView]:
    return result(request, service.revoke(identifier, request, uow), response)
