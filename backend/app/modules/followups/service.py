from datetime import timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy import select, update

from app.modules.cases import repository as cases
from app.modules.cases.models import Case
from app.modules.customers import repository as customers
from app.modules.followups import repository as repo
from app.modules.followups.models import Feedback, Task
from app.modules.followups.schemas import ResolutionFeedback, TaskCreate, TaskPatch
from app.modules.identity.models import Membership
from app.modules.workspace.models import Workspace
from app.platform import idempotency
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role
from app.platform.protocol import Fault, match_version, missing, now


def eligible(uow: UnitOfWork, identifier: UUID | None, manager: bool = False) -> bool:
    member = uow.session.get(Membership, identifier) if identifier else None
    roles = {"admin", "manager"} if manager else {"admin", "manager", "agent"}
    return bool(member and member.active and member.role in roles)


def task_audit(
    uow: UnitOfWork, row: Task, action: str, fields: list[str], request: Request
) -> None:
    record_audit(
        uow.session,
        row.workspace_id,
        uow.scope.user_id,
        action,
        "task",
        row.id,
        fields,
        request.state.request_id,
        actor_kind=uow.scope.audience,
    )


def create_task(uow: UnitOfWork, payload: TaskCreate, request: Request) -> Task:
    require_role(uow.scope, "admin", "manager", "agent")
    customer = customers.customer(uow.session, payload.customer_id)
    if payload.case_id:
        case = cases.get_case(uow, payload.case_id)
        if case.customer_id != customer.id:
            raise Fault(422, "case_customer_mismatch", "Choose a case belonging to this customer.")
    replay, exists = idempotency.prepare(uow, request, payload)
    if exists:
        assert replay.resource_id
        return repo.task(uow, replay.resource_id)
    if customer.archived_at:
        raise Fault(409, "archived", "Choose an active customer.")
    if not eligible(uow, payload.assignee_member_id):
        raise Fault(
            422, "invalid_assignee", "Choose an active staff member who can own follow-ups."
        )
    row = Task(
        workspace_id=uow.scope.workspace_id,
        created_by_member_id=uow.scope.member_id,
        **payload.model_dump(),
    )
    uow.session.add(row)
    uow.session.flush()
    task_audit(uow, row, "task.created", list(payload.model_fields_set), request)
    idempotency.complete(replay, "task", row.id, 201)
    return row


def change_task(uow: UnitOfWork, identifier: UUID, payload: TaskPatch, request: Request) -> Task:
    require_role(uow.scope, "admin", "manager", "agent")
    row = repo.task(uow, identifier, True)
    match_version(request, row.version)
    state = payload.state or row.state
    assignee = payload.assignee_member_id or row.assignee_member_id
    if (payload.assignee_member_id or state in repo.INCOMPLETE) and not eligible(uow, assignee):
        raise Fault(
            422, "invalid_assignee", "Choose an active staff member who can own follow-ups."
        )
    if state in repo.INCOMPLETE and customers.customer(uow.session, row.customer_id).archived_at:
        raise Fault(409, "archived", "An archived customer cannot have active follow-ups.")
    instant = now()
    old_state = row.state
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    if payload.state == "completed":
        row.completed_at = instant
        row.completed_by_member_id = uow.scope.member_id
    elif state != "completed":
        row.completed_at = row.completed_by_member_id = row.completion_note = None
    row.version += 1
    row.updated_at = instant
    action = "task.updated"
    if payload.state == "completed":
        action = "task.completed"
    elif old_state == "completed" and state in repo.INCOMPLETE:
        action = "task.reopened"
    elif payload.state == "cancelled":
        action = "task.cancelled"
    task_audit(uow, row, action, list(payload.model_fields_set), request)
    uow.session.flush()
    return row


def already_rated(uow: UnitOfWork, case: Case, cycle: int) -> bool:
    return (
        uow.session.scalar(
            select(Feedback.id).where(
                Feedback.case_id == case.id,
                Feedback.cycle_number == cycle,
            )
        )
        is not None
    )


def rate(
    uow: UnitOfWork,
    identifier: UUID,
    cycle: int,
    payload: ResolutionFeedback,
    request: Request,
) -> Feedback:
    if uow.scope.audience != "portal":
        raise Fault(403, "forbidden", "Use the customer portal to rate this resolution.")
    case = cases.get_case(uow, identifier)
    with cases.case_storage(uow):
        case = cases.get_case(uow, identifier, True)
        replay, exists = idempotency.prepare(uow, request, payload)
        if exists:
            prior = uow.session.get(Feedback, replay.resource_id)
            if (
                not prior
                or prior.case_id != case.id
                or prior.requester_contact_id != uow.scope.contact_id
            ):
                raise missing()
            return prior
        if already_rated(uow, case, cycle):
            raise Fault(409, "feedback_exists", "This resolution already has a rating.")
        match_version(request, case.version)
        if case.state != "resolved" or case.current_cycle_number != cycle:
            raise Fault(409, "feedback_unavailable", "Only the latest resolved cycle can be rated.")
        if not cases.current_cycle(uow, case).resolved_at:
            raise Fault(409, "feedback_unavailable", "This cycle has not been resolved.")
        instant = now()
        row = Feedback(
            workspace_id=case.workspace_id,
            case_id=case.id,
            cycle_number=cycle,
            requester_contact_id=case.requester_contact_id,
            rating=payload.rating,
            comment=payload.comment,
            created_at=instant,
        )
        uow.session.add(row)
        uow.session.flush()
        record_audit(
            uow.session,
            row.workspace_id,
            uow.scope.user_id,
            "feedback.submitted",
            "feedback",
            row.id,
            ["rating", "comment"],
            request.state.request_id,
            actor_kind="portal",
        )
        if row.rating <= 2:
            customer = customers.customer(uow.session, case.customer_id)
            workspace = uow.session.get(Workspace, uow.scope.workspace_id)
            assert workspace
            assignee = next(
                (
                    member
                    for member in (case.assignee_member_id, customer.owner_member_id)
                    if eligible(uow, member)
                ),
                workspace.feedback_manager_member_id,
            )
            # Workspace bootstrap, publication, and membership changes maintain this invariant.
            assert assignee is not None
            task = Task(
                workspace_id=case.workspace_id,
                customer_id=case.customer_id,
                case_id=case.id,
                feedback_id=row.id,
                title="Review low resolution rating",
                description=f"Review case CX-{case.number:06d}, resolution cycle {cycle}.",
                assignee_member_id=assignee,
                due_at=instant + timedelta(hours=48),
                created_at=instant,
                updated_at=instant,
            )
            uow.session.add(task)
            uow.session.flush()
            task_audit(
                uow,
                task,
                "task.created_from_feedback",
                ["feedback_id", "assignee_member_id", "due_at"],
                request,
            )
        case.version += 1
        case.updated_at = instant
        idempotency.complete(replay, "feedback", row.id, 201)
    return row


def has_incomplete_tasks(
    uow: UnitOfWork, *, customer_id: UUID | None = None, member_id: UUID | None = None
) -> bool:
    query = select(Task.id).where(Task.state.in_(repo.INCOMPLETE))
    if customer_id:
        query = query.where(Task.customer_id == customer_id)
    if member_id:
        query = query.where(Task.assignee_member_id == member_id)
    return uow.session.scalar(query.limit(1)) is not None


def transfer(uow: UnitOfWork, member_id: UUID, replacement_id: UUID, request: Request) -> None:
    rows = uow.session.scalars(
        update(Task)
        .where(Task.assignee_member_id == member_id, Task.state.in_(repo.INCOMPLETE))
        .values(assignee_member_id=replacement_id, updated_at=now(), version=Task.version + 1)
        .returning(Task)
    )
    for row in rows:
        task_audit(uow, row, "task.assignee_reassigned", ["assignee_member_id"], request)
