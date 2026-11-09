from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, select, tuple_

from app.modules.cases.models import Case
from app.modules.cases.schemas import Reference
from app.modules.customers.models import Customer
from app.modules.followups.models import Feedback, Task
from app.modules.followups.schemas import (
    FeedbackView,
    PageFilters,
    StaffFeedbackView,
    TaskState,
    TaskView,
)
from app.modules.identity.models import Membership, User
from app.platform.audit import AuditEvent
from app.platform.auth import UnitOfWork
from app.platform.protocol import Fault, missing, now, read_cursor, sign_cursor

INCOMPLETE = ("open", "in_progress")


def task(uow: UnitOfWork, identifier: UUID, lock: bool = False) -> Task:
    row = uow.session.get(Task, identifier, with_for_update=lock)
    if not row:
        raise missing()
    return row


def task_view(uow: UnitOfWork, row: Task) -> TaskView:
    customer = uow.session.get(Customer, row.customer_id)
    case = uow.session.get(Case, row.case_id) if row.case_id else None
    member = uow.session.get(Membership, row.assignee_member_id)
    user = uow.session.get(User, member.user_id) if member else None
    assert customer and user
    return TaskView(
        id=row.id,
        version=row.version,
        title=row.title,
        description=row.description,
        customer=Reference(id=customer.id, name=customer.name),
        case=Reference(id=case.id, name=case.subject) if case else None,
        feedback_id=row.feedback_id,
        assignee=Reference(id=row.assignee_member_id, name=user.display_name),
        due_at=row.due_at,
        state=cast(TaskState, row.state),
        overdue=row.state in INCOMPLETE and row.due_at < now(),
        completed_at=row.completed_at,
        completed_by_member_id=row.completed_by_member_id,
        completion_note=row.completion_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def feedback_view(row: Feedback) -> FeedbackView:
    return FeedbackView(
        id=row.id,
        cycle_number=row.cycle_number,
        rating=row.rating,
        comment=row.comment,
        created_at=row.created_at,
    )


def staff_feedback_view(uow: UnitOfWork, row: Feedback) -> StaffFeedbackView:
    case = uow.session.get(Case, row.case_id)
    assert case
    customer = uow.session.get(Customer, case.customer_id)
    assert customer
    task_id = uow.session.scalar(select(Task.id).where(Task.feedback_id == row.id))
    return StaffFeedbackView(
        **feedback_view(row).model_dump(),
        customer=Reference(id=customer.id, name=customer.name),
        case=Reference(id=case.id, name=case.subject),
        task_id=task_id,
    )


def page[T: Task | Feedback | AuditEvent](
    uow: UnitOfWork,
    query: Select[tuple[T]],
    model: Any,
    filters: PageFilters,
    resource: str,
    sort: str = "created_at",
    ascending: bool = False,
) -> tuple[list[T], str | None]:
    column = getattr(model, sort)
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "resource": resource,
        "audience": uow.scope.audience,
        "contact": str(uow.scope.contact_id),
        "filters": filters.model_dump(mode="json", exclude={"cursor", "limit"}),
    }
    if filters.cursor:
        try:
            stamp, identifier = read_cursor(filters.cursor, binding)
            boundary = (datetime.fromisoformat(stamp), UUID(identifier))
            columns = tuple_(column, model.id)
            query = query.where(columns > boundary if ascending else columns < boundary)
        except (TypeError, ValueError):
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    order = (column.asc(), model.id.asc()) if ascending else (column.desc(), model.id.desc())
    rows = list(uow.session.scalars(query.order_by(*order).limit(filters.limit + 1)))
    result = rows[: filters.limit]
    cursor = (
        sign_cursor(binding, [getattr(result[-1], sort).isoformat(), str(result[-1].id)])
        if len(rows) > filters.limit
        else None
    )
    return result, cursor
