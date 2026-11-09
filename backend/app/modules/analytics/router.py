from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.modules.analytics import service
from app.modules.analytics.schemas import (
    ExportFilters,
    MetricRecord,
    Overview,
    RecordFilters,
    TrendFilters,
    Trends,
)
from app.modules.cases.router import listing
from app.platform.auth import UnitOfWork, require_role
from app.platform.protocol import Envelope, result

router = APIRouter(prefix="/analytics", tags=["operational analytics"])
ReportUnit = Annotated[UnitOfWork, Depends(service.report_uow)]


@router.get("/overview")
def overview(
    filters: Annotated[TrendFilters, Query()], request: Request, uow: ReportUnit
) -> Envelope[Overview]:
    return result(
        request, service.overview(uow, service.report_scope(uow, filters), filters.bucket)
    )


@router.get("/trends")
def trends(
    filters: Annotated[TrendFilters, Query()], request: Request, uow: ReportUnit
) -> Envelope[Trends]:
    return result(request, service.trends(uow, service.report_scope(uow, filters), filters.bucket))


@router.get("/records")
def records(
    filters: Annotated[RecordFilters, Query()], request: Request, uow: ReportUnit
) -> Envelope[list[MetricRecord]]:
    require_role(uow.scope, "admin", "manager")
    rows, cursor = service.records(uow, service.report_scope(uow, filters), filters)
    return listing(request, rows, cursor)


@router.get("/export", responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}})
def export(
    filters: Annotated[ExportFilters, Query()], request: Request, uow: ReportUnit
) -> Response:
    require_role(uow.scope, "admin", "manager")
    content = service.export(
        uow, service.report_scope(uow, filters), filters, request.state.request_id
    )
    return Response(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="atlas-{filters.report}.csv"'},
    )
