from collections.abc import Iterator
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import literal, select, tuple_

from app.modules.cases import repository as repo
from app.modules.cases import service
from app.modules.cases.models import CaseTransition
from app.modules.cases.schemas import (
    CaseCreatePortal,
    CaseCreateStaff,
    CaseDetail,
    CasePatch,
    CaseSummary,
    ConfigView,
    HistoryFilters,
    HistoryView,
    ListFilters,
    MessageCreate,
    MessageFilters,
    MessageView,
    PortalCaseDetail,
    PortalCaseSummary,
    PortalConfig,
    PortalFilters,
    PortalMessageCreate,
    PortalMessageView,
    ReadInput,
    ReopenInput,
    TransitionInput,
    TransitionResult,
)
from app.modules.workspace.case_config_models import CaseConfig
from app.modules.workspace.case_configuration import public_config, published
from app.modules.workspace.models import Workspace
from app.platform.audit import AuditEvent
from app.platform.auth import UnitOfWork, authenticated_uow, staff_uow
from app.platform.protocol import Envelope, Fault, Meta, missing, read_cursor, result, sign_cursor

router = APIRouter(tags=["cases"])
Staff = Annotated[UnitOfWork, Depends(staff_uow, scope="function")]


def portal_uow(request: Request) -> Iterator[UnitOfWork]:
    for uow in authenticated_uow(request):
        if uow.scope.audience != "portal":
            raise Fault(403, "forbidden", "Use a customer portal account for this page.")
        yield uow


Portal = Annotated[UnitOfWork, Depends(portal_uow, scope="function")]


def listing[T](request: Request, data: list[T], cursor: str | None) -> Envelope[list[T]]:
    return Envelope(
        data=data,
        meta=Meta(
            request_id=request.state.request_id, next_cursor=cursor, has_more=cursor is not None
        ),
    )


@router.get("/case-configs", response_model=Envelope[list[ConfigView]])
def configs(request: Request, uow: Staff) -> Envelope[list[ConfigView]]:
    rows = uow.session.scalars(
        select(CaseConfig).where(CaseConfig.status == "published").order_by(CaseConfig.number)
    )
    data = [
        ConfigView(
            id=row.id,
            version=row.version,
            number=row.number,
            status="published",
            definition=published(uow.session, row.id)[1],
            published_at=row.published_at,
        )
        for row in rows
    ]
    return result(request, data)


@router.get("/case-configs/{identifier}", response_model=Envelope[ConfigView])
def config_detail(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[ConfigView]:
    row = uow.session.get(CaseConfig, identifier)
    if not row or row.status != "published":
        raise missing()
    assert row.published_at
    return result(
        request,
        ConfigView(
            id=row.id,
            version=row.version,
            number=row.number,
            status="published",
            definition=published(uow.session, row.id)[1],
            published_at=row.published_at,
        ),
        response,
    )


@router.get("/cases", response_model=Envelope[list[CaseSummary]])
def cases(
    request: Request, filters: Annotated[ListFilters, Query()], uow: Staff
) -> Envelope[list[CaseSummary]]:
    rows, cursor = repo.page_cases(uow, filters)
    return listing(request, repo.staff_summaries(uow, rows), cursor)


@router.post("/cases", status_code=201, response_model=Envelope[CaseDetail])
def create_case(
    payload: CaseCreateStaff, request: Request, response: Response, uow: Staff
) -> Envelope[CaseDetail]:
    row = service.create(uow, payload, request)
    response.headers["Location"] = f"/api/v1/cases/{row.id}"
    return result(request, repo.detail(uow, row), response)


@router.get("/cases/{identifier}", response_model=Envelope[CaseDetail])
def case(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[CaseDetail]:
    return result(request, repo.detail(uow, repo.get_case(uow, identifier)), response)


@router.patch("/cases/{identifier}", response_model=Envelope[CaseDetail])
def patch_case(
    identifier: UUID, payload: CasePatch, request: Request, response: Response, uow: Staff
) -> Envelope[CaseDetail]:
    return result(
        request, repo.detail(uow, service.patch(uow, identifier, payload, request)), response
    )


@router.post("/cases/{identifier}/transitions", response_model=Envelope[TransitionResult])
def transition(
    identifier: UUID, payload: TransitionInput, request: Request, response: Response, uow: Staff
) -> Envelope[TransitionResult]:
    row, event, message = service.transition(uow, identifier, payload, request)
    response.headers["ETag"] = f'"{row.version}"'
    return result(
        request,
        TransitionResult(
            case=repo.detail(uow, row),
            transition_id=event.id,
            message_id=message.id if message else None,
        ),
    )


@router.get("/cases/{identifier}/messages", response_model=Envelope[list[MessageView]])
def messages(
    identifier: UUID, request: Request, filters: Annotated[MessageFilters, Query()], uow: Staff
) -> Envelope[list[MessageView]]:
    data, cursor = repo.list_messages(uow, repo.get_case(uow, identifier), filters)
    return listing(request, data, cursor)


@router.post("/cases/{identifier}/messages", response_model=Envelope[MessageView])
def post_message(
    identifier: UUID, payload: MessageCreate, request: Request, response: Response, uow: Staff
) -> Envelope[MessageView]:
    row, message = service.post_message(uow, identifier, payload, request)
    response.headers["ETag"] = f'"{row.version}"'
    return result(request, repo.message_view(uow, message, row.version))


@router.post("/cases/{identifier}/read-marker", response_model=Envelope[ReadInput])
def mark_read(
    identifier: UUID, payload: ReadInput, request: Request, uow: Staff
) -> Envelope[ReadInput]:
    return result(
        request, ReadInput(last_read_sequence=service.mark_read(uow, identifier, payload))
    )


@router.get("/cases/{identifier}/history", response_model=Envelope[list[HistoryView]])
def history(
    identifier: UUID, request: Request, filters: Annotated[HistoryFilters, Query()], uow: Staff
) -> Envelope[list[HistoryView]]:
    repo.get_case(uow, identifier)
    binding = {"workspace": str(uow.scope.workspace_id), "resource": f"case-history:{identifier}"}
    transitions = select(CaseTransition).where(CaseTransition.case_id == identifier)
    audits = select(AuditEvent).where(
        AuditEvent.entity_type == "case", AuditEvent.entity_id == identifier
    )
    if filters.cursor:
        try:
            stamp, cursor_id = read_cursor(filters.cursor, binding)
            boundary = tuple_(literal(datetime.fromisoformat(stamp)), literal(UUID(cursor_id)))
            transitions = transitions.where(
                tuple_(CaseTransition.occurred_at, CaseTransition.id) < boundary
            )
            audits = audits.where(tuple_(AuditEvent.occurred_at, AuditEvent.id) < boundary)
        except (ValueError, TypeError):
            raise Fault(400, "invalid_cursor", "Return to the first history page.") from None
    events = [
        HistoryView(
            id=row.id,
            kind="transition",
            occurred_at=row.occurred_at,
            action="case.transition",
            from_state=row.from_state,
            to_state=row.to_state,
            cycle_number=row.cycle_number,
            reason=row.reason,
        )
        for row in uow.session.scalars(
            transitions.order_by(CaseTransition.occurred_at.desc(), CaseTransition.id.desc()).limit(
                filters.limit + 1
            )
        )
    ]
    events.extend(
        HistoryView(
            id=row.id,
            kind="audit",
            occurred_at=row.occurred_at,
            action=row.action,
            changed_fields=row.changed_fields,
        )
        for row in uow.session.scalars(
            audits.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(
                filters.limit + 1
            )
        )
    )
    events.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
    more = len(events) > filters.limit
    events = events[: filters.limit]
    cursor = (
        sign_cursor(binding, [events[-1].occurred_at.isoformat(), str(events[-1].id)])
        if more
        else None
    )
    return listing(request, events, cursor)


@router.get("/portal/config", response_model=Envelope[PortalConfig])
def portal_config(request: Request, uow: Portal) -> Envelope[PortalConfig]:
    with repo.case_storage(uow):
        workspace = uow.session.get(Workspace, uow.scope.workspace_id)
        assert workspace
        return result(
            request, public_config(published(uow.session, workspace.active_case_config_id)[1], True)
        )


@router.get("/portal/cases", response_model=Envelope[list[PortalCaseSummary]])
def portal_cases(
    request: Request, filters: Annotated[PortalFilters, Query()], uow: Portal
) -> Envelope[list[PortalCaseSummary]]:
    rows, cursor = repo.page_cases(uow, filters)
    return listing(request, [repo.portal_summary(uow, row) for row in rows], cursor)


@router.post("/portal/cases", status_code=201, response_model=Envelope[PortalCaseDetail])
def portal_create(
    payload: CaseCreatePortal, request: Request, response: Response, uow: Portal
) -> Envelope[PortalCaseDetail]:
    row = service.create(uow, payload, request)
    response.headers["Location"] = f"/api/v1/portal/cases/{row.id}"
    return result(request, repo.portal_detail(uow, row), response)


@router.get("/portal/cases/{identifier}", response_model=Envelope[PortalCaseDetail])
def portal_case(
    identifier: UUID, request: Request, response: Response, uow: Portal
) -> Envelope[PortalCaseDetail]:
    return result(request, repo.portal_detail(uow, repo.get_case(uow, identifier)), response)


@router.get("/portal/cases/{identifier}/messages", response_model=Envelope[list[PortalMessageView]])
def portal_messages(
    identifier: UUID, request: Request, filters: Annotated[MessageFilters, Query()], uow: Portal
) -> Envelope[list[PortalMessageView]]:
    data, cursor = repo.list_messages(uow, repo.get_case(uow, identifier), filters)
    return listing(
        request, [PortalMessageView.model_validate(item.model_dump()) for item in data], cursor
    )


@router.post("/portal/cases/{identifier}/messages", response_model=Envelope[PortalMessageView])
def portal_message(
    identifier: UUID,
    payload: PortalMessageCreate,
    request: Request,
    response: Response,
    uow: Portal,
) -> Envelope[PortalMessageView]:
    row, message = service.post_message(uow, identifier, payload, request)
    response.headers["ETag"] = f'"{row.version}"'
    return result(
        request,
        PortalMessageView.model_validate(repo.message_view(uow, message, row.version).model_dump()),
    )


@router.post("/portal/cases/{identifier}/reopen", response_model=Envelope[PortalCaseDetail])
def portal_reopen(
    identifier: UUID, payload: ReopenInput, request: Request, response: Response, uow: Portal
) -> Envelope[PortalCaseDetail]:
    row, _, _ = service.transition(uow, identifier, payload, request)
    return result(request, repo.portal_detail(uow, row), response)
