from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.modules.activities import repository
from app.modules.activities.schemas import EventFilters, EventView, TimelineEntry, TimelineFilters
from app.modules.cases.router import Staff, listing
from app.platform.protocol import Envelope, result

router = APIRouter(tags=["customer activity"])


@router.get("/customers/{customer_id}/events")
def events(
    customer_id: UUID, filters: Annotated[EventFilters, Query()], request: Request, uow: Staff
) -> Envelope[list[EventView]]:
    return listing(request, *repository.events(uow, customer_id, filters))


@router.get("/customers/{customer_id}/events/{event_id}")
def event_detail(
    customer_id: UUID, event_id: UUID, request: Request, uow: Staff
) -> Envelope[EventView]:
    return result(request, repository.event_detail(uow, customer_id, event_id))


@router.get("/customers/{customer_id}/timeline")
def timeline(
    customer_id: UUID, filters: Annotated[TimelineFilters, Query()], request: Request, uow: Staff
) -> Envelope[list[TimelineEntry]]:
    return listing(request, *repository.timeline(uow, customer_id, filters))
