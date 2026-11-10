from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.modules.customers import repository, service
from app.modules.customers.schemas import (
    ArchiveInput,
    ContactCreate,
    ContactFilters,
    ContactPatch,
    ContactView,
    CustomerCreate,
    CustomerFilters,
    CustomerPatch,
    CustomerView,
)
from app.platform.auth import UnitOfWork, staff_uow
from app.platform.protocol import Envelope, Meta, result

router = APIRouter(tags=["customers"])
Uow = Annotated[UnitOfWork, Depends(staff_uow, scope="function")]


@router.get("/customers", response_model=Envelope[list[CustomerView]])
def customers(
    request: Request, filters: Annotated[CustomerFilters, Query()], uow: Uow
) -> Envelope[list[CustomerView]]:
    rows, cursor = repository.page_customers(uow.session, uow.scope.workspace_id, filters)
    return Envelope(
        data=rows,
        meta=Meta(
            request_id=request.state.request_id, next_cursor=cursor, has_more=cursor is not None
        ),
    )


@router.post("/customers", status_code=201, response_model=Envelope[CustomerView])
def create_customer(
    payload: CustomerCreate, request: Request, response: Response, uow: Uow
) -> Envelope[CustomerView]:
    data = service.save_customer(uow, payload, request)
    response.headers["Location"] = f"/api/v1/customers/{data.id}"
    return result(request, data, response)


@router.get("/customers/{identifier}", response_model=Envelope[CustomerView])
def get_customer(
    identifier: UUID, request: Request, response: Response, uow: Uow
) -> Envelope[CustomerView]:
    return result(
        request,
        repository.customer_view(uow.session, repository.customer(uow.session, identifier)),
        response,
    )


@router.patch("/customers/{identifier}", response_model=Envelope[CustomerView])
def update_customer(
    identifier: UUID, payload: CustomerPatch, request: Request, response: Response, uow: Uow
) -> Envelope[CustomerView]:
    return result(request, service.save_customer(uow, payload, request, identifier), response)


@router.post("/customers/{identifier}/archive", response_model=Envelope[CustomerView])
def archive_customer(
    identifier: UUID, payload: ArchiveInput, request: Request, response: Response, uow: Uow
) -> Envelope[CustomerView]:
    return result(
        request, cast(CustomerView, service.archive(uow, identifier, payload, request)), response
    )


@router.get("/contacts", response_model=Envelope[list[ContactView]])
def contacts(
    request: Request, filters: Annotated[ContactFilters, Query()], uow: Uow
) -> Envelope[list[ContactView]]:
    rows, cursor = repository.page_contacts(uow.session, uow.scope.workspace_id, filters)
    return Envelope(
        data=rows,
        meta=Meta(
            request_id=request.state.request_id, next_cursor=cursor, has_more=cursor is not None
        ),
    )


@router.post("/contacts", status_code=201, response_model=Envelope[ContactView])
def create_contact(
    payload: ContactCreate, request: Request, response: Response, uow: Uow
) -> Envelope[ContactView]:
    data = service.save_contact(uow, payload, request)
    response.headers["Location"] = f"/api/v1/contacts/{data.id}"
    return result(request, data, response)


@router.get("/contacts/{identifier}", response_model=Envelope[ContactView])
def get_contact(
    identifier: UUID, request: Request, response: Response, uow: Uow
) -> Envelope[ContactView]:
    return result(
        request,
        repository.contact_view(uow.session, repository.contact(uow.session, identifier)),
        response,
    )


@router.patch("/contacts/{identifier}", response_model=Envelope[ContactView])
def update_contact(
    identifier: UUID, payload: ContactPatch, request: Request, response: Response, uow: Uow
) -> Envelope[ContactView]:
    return result(request, service.save_contact(uow, payload, request, identifier), response)


@router.post("/contacts/{identifier}/archive", response_model=Envelope[ContactView])
def archive_contact(
    identifier: UUID, payload: ArchiveInput, request: Request, response: Response, uow: Uow
) -> Envelope[ContactView]:
    return result(
        request,
        cast(ContactView, service.archive(uow, identifier, payload, request, True)),
        response,
    )
