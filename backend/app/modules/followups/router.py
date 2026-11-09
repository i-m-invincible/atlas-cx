from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, Request, Response
from sqlalchemy import and_, not_, select

from app.modules.cases import repository as cases
from app.modules.cases.models import Case
from app.modules.cases.router import Portal, Staff, listing
from app.modules.followups import repository as repo
from app.modules.followups import service
from app.modules.followups.models import Feedback, Task
from app.modules.followups.schemas import (
    FeedbackFilters,
    FeedbackView,
    PageFilters,
    ResolutionFeedback,
    StaffFeedbackView,
    TaskCreate,
    TaskFilters,
    TaskHistory,
    TaskPatch,
    TaskView,
)
from app.modules.identity.models import User
from app.platform.audit import AuditEvent
from app.platform.protocol import Envelope, now, result

router = APIRouter(tags=["follow-ups"])


@router.get("/tasks")
def tasks(
    request: Request, filters: Annotated[TaskFilters, Query()], uow: Staff
) -> Envelope[list[TaskView]]:
    query = select(Task)
    for key in ("customer_id", "case_id", "assignee_id"):
        value = getattr(filters, key)
        if value:
            column = Task.assignee_member_id if key == "assignee_id" else getattr(Task, key)
            query = query.where(column == value)
    if filters.state:
        query = query.where(Task.state.in_(filters.state.split(",")))
    if filters.overdue is not None:
        overdue = and_(Task.state.in_(repo.INCOMPLETE), Task.due_at < now())
        query = query.where(overdue if filters.overdue else not_(overdue))
    rows, cursor = repo.page(
        uow, query, Task, filters, "tasks", filters.sort, filters.sort == "due_at"
    )
    return listing(request, [repo.task_view(uow, row) for row in rows], cursor)


@router.get("/tasks/{identifier}")
def task(identifier: UUID, request: Request, response: Response, uow: Staff) -> Envelope[TaskView]:
    return result(request, repo.task_view(uow, repo.task(uow, identifier)), response)


@router.get("/tasks/{identifier}/history")
def history(
    identifier: UUID,
    request: Request,
    filters: Annotated[PageFilters, Query()],
    uow: Staff,
) -> Envelope[list[TaskHistory]]:
    repo.task(uow, identifier)
    query = select(AuditEvent).where(
        AuditEvent.entity_type == "task", AuditEvent.entity_id == identifier
    )
    rows, cursor = repo.page(
        uow, query, AuditEvent, filters, f"task-history:{identifier}", "occurred_at"
    )
    authors = dict(
        uow.session.execute(
            select(User.id, User.display_name).where(
                User.id.in_({row.actor_user_id for row in rows if row.actor_user_id})
            )
        )
        .tuples()
        .all()
    )
    return listing(
        request,
        [
            TaskHistory(
                id=row.id,
                action=row.action,
                occurred_at=row.occurred_at,
                actor_name=authors.get(row.actor_user_id) if row.actor_user_id else None,
                changed_fields=row.changed_fields,
            )
            for row in rows
        ],
        cursor,
    )


@router.post("/tasks", status_code=201)
def create(
    payload: TaskCreate, request: Request, response: Response, uow: Staff
) -> Envelope[TaskView]:
    row = service.create_task(uow, payload, request)
    response.headers["Location"] = f"/api/v1/tasks/{row.id}"
    return result(request, repo.task_view(uow, row), response)


@router.patch("/tasks/{identifier}")
def change(
    identifier: UUID, payload: TaskPatch, request: Request, response: Response, uow: Staff
) -> Envelope[TaskView]:
    return result(
        request,
        repo.task_view(uow, service.change_task(uow, identifier, payload, request)),
        response,
    )


@router.get("/feedback")
def feedback(
    request: Request, filters: Annotated[FeedbackFilters, Query()], uow: Staff
) -> Envelope[list[StaffFeedbackView]]:
    query = select(Feedback)
    if filters.customer_id:
        query = query.join(Case, Feedback.case_id == Case.id).where(
            Case.customer_id == filters.customer_id
        )
    if filters.case_id:
        query = query.where(Feedback.case_id == filters.case_id)
    if filters.rating:
        query = query.where(Feedback.rating.in_([int(item) for item in filters.rating.split(",")]))
    if filters.from_:
        query = query.where(Feedback.created_at >= filters.from_)
    if filters.to:
        query = query.where(Feedback.created_at < filters.to)
    rows, cursor = repo.page(uow, query, Feedback, filters, "feedback")
    return listing(request, [repo.staff_feedback_view(uow, row) for row in rows], cursor)


@router.get("/portal/cases/{identifier}/feedback")
def portal_feedback(
    identifier: UUID,
    request: Request,
    filters: Annotated[PageFilters, Query()],
    uow: Portal,
) -> Envelope[list[FeedbackView]]:
    case = cases.get_case(uow, identifier)
    query = select(Feedback).where(
        Feedback.case_id == case.id, Feedback.requester_contact_id == uow.scope.contact_id
    )
    rows, cursor = repo.page(uow, query, Feedback, filters, f"portal-feedback:{case.id}")
    return listing(request, [repo.feedback_view(row) for row in rows], cursor)


@router.post("/portal/cases/{identifier}/cycles/{cycle}/feedback", status_code=201)
def rate(
    identifier: UUID,
    cycle: Annotated[int, Path(ge=1, le=2147483647)],
    payload: ResolutionFeedback,
    request: Request,
    response: Response,
    uow: Portal,
) -> Envelope[FeedbackView]:
    row = service.rate(uow, identifier, cycle, payload, request)
    response.headers["Location"] = f"/api/v1/portal/cases/{identifier}/feedback"
    return result(request, repo.feedback_view(row))
