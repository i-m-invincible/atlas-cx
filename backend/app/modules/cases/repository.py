from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import String, exists, func, literal, or_, select, tuple_
from sqlalchemy import case as sql_case
from sqlalchemy import cast as sql_cast
from sqlalchemy.sql.selectable import Exists

from app.modules.cases.clocks import clock
from app.modules.cases.models import Case, CaseCycle, Message, ReadMarker
from app.modules.cases.schemas import (
    CaseDetail,
    CaseSummary,
    CycleView,
    Definition,
    ListFilters,
    MessageFilters,
    MessageView,
    PortalCaseDetail,
    PortalCaseSummary,
    PortalFilters,
    State,
)
from app.modules.customers.models import Contact, Customer
from app.modules.followups.models import Feedback
from app.modules.identity.models import Membership, User
from app.modules.workspace.case_config_models import CaseConfig
from app.modules.workspace.case_configuration import public_config, published
from app.modules.workspace.team_models import Team
from app.platform.auth import UnitOfWork
from app.platform.database import set_scope
from app.platform.protocol import Fault, missing, now, read_cursor, sign_cursor


@contextmanager
def case_storage(uow: UnitOfWork) -> Iterator[None]:
    """A verified portal operation may write its bounded case transaction.

    Portal RLS itself remains read-only/public-only. Callers must resolve the
    owned case/contact before entering; no unverified client scope is accepted.
    Nested projection calls share the outer transaction scope.
    """
    if uow.scope.audience == "staff":
        yield
        return
    depth = int(uow.session.info.get("case_storage_depth", 0))
    uow.session.info["case_storage_depth"] = depth + 1
    if depth == 0:
        set_scope(
            uow.session, uow.scope.workspace_id, "staff", uow.scope.user_id, uow.scope.contact_id
        )
    try:
        yield
        if depth == 0:
            uow.session.flush()
    finally:
        uow.session.info["case_storage_depth"] = depth
        if depth == 0 and uow.session.is_active:
            with uow.session.no_autoflush:
                set_scope(
                    uow.session,
                    uow.scope.workspace_id,
                    "portal",
                    uow.scope.user_id,
                    uow.scope.contact_id,
                )


def get_case(uow: UnitOfWork, identifier: UUID, lock: bool = False) -> Case:
    query = select(Case).where(Case.id == identifier, Case.workspace_id == uow.scope.workspace_id)
    if uow.scope.audience == "portal":
        query = query.where(Case.requester_contact_id == uow.scope.contact_id)
    # Portal callers only lock after ownership is established under portal RLS.
    row = uow.session.scalar(query.with_for_update() if lock else query)
    if not row:
        raise missing()
    return row


def current_cycle(uow: UnitOfWork, row: Case) -> CaseCycle:
    cycle = uow.session.scalar(
        select(CaseCycle).where(
            CaseCycle.case_id == row.id, CaseCycle.cycle_number == row.current_cycle_number
        )
    )
    assert cycle
    return cycle


def cycle_view(row: CaseCycle) -> CycleView:
    return CycleView.model_validate({key: getattr(row, key) for key in CycleView.model_fields})


def unread_query(uow: UnitOfWork) -> Exists:
    marker = (
        select(ReadMarker.last_read_sequence)
        .where(
            ReadMarker.case_id == Case.id,
            ReadMarker.member_id == uow.scope.member_id,
        )
        .correlate(Case)
        .scalar_subquery()
    )
    return exists(
        select(Message.id).where(
            Message.case_id == Case.id,
            Message.author_kind != "system",
            or_(Message.author_user_id != uow.scope.user_id, Message.author_user_id.is_(None)),
            Message.sequence > func.coalesce(marker, 0),
        )
    )


def staff_summaries(uow: UnitOfWork, rows: list[Case]) -> list[CaseSummary]:
    if not rows:
        return []
    session = uow.session
    ids = [row.id for row in rows]
    customers = {
        row.id: row
        for row in session.scalars(
            select(Customer).where(Customer.id.in_([row.customer_id for row in rows]))
        )
    }
    contacts = {
        row.id: row
        for row in session.scalars(
            select(Contact).where(Contact.id.in_([row.requester_contact_id for row in rows]))
        )
    }
    owners = {
        member_id: name
        for member_id, name in session.execute(
            select(Membership.id, User.display_name)
            .join(User, Membership.user_id == User.id)
            .where(
                Membership.id.in_(
                    [row.assignee_member_id for row in rows if row.assignee_member_id]
                )
            )
        ).all()
    }
    teams = {
        row.id: row
        for row in session.scalars(
            select(Team).where(Team.id.in_([row.team_id for row in rows if row.team_id]))
        )
    }
    configs = {
        row.id: Definition.model_validate(row.definition_json)
        for row in session.scalars(
            select(CaseConfig).where(CaseConfig.id.in_([row.config_version_id for row in rows]))
        )
    }
    cycles = {
        row.case_id: row
        for row in session.scalars(
            select(CaseCycle)
            .join(
                Case,
                (CaseCycle.case_id == Case.id)
                & (CaseCycle.cycle_number == Case.current_cycle_number),
            )
            .where(Case.id.in_(ids))
        )
    }
    unread_ids = set(session.scalars(select(Case.id).where(Case.id.in_(ids), unread_query(uow))))
    instant = now()
    result = []
    for row in rows:
        definition, cycle = configs[row.config_version_id], cycles[row.id]
        category = next(item for item in definition.categories if item.key == row.category_key)
        result.append(
            CaseSummary.model_validate(
                {
                    "id": row.id,
                    "number": row.number,
                    "version": row.version,
                    "subject": row.subject,
                    "state": row.state,
                    "state_label": definition.state_labels[cast(State, row.state)],
                    "category_key": row.category_key,
                    "category_label": category.label,
                    "priority": row.priority,
                    "customer": {"id": row.customer_id, "name": customers[row.customer_id].name},
                    "requester": {
                        "id": row.requester_contact_id,
                        "name": contacts[row.requester_contact_id].name,
                    },
                    "assignee": {
                        "id": row.assignee_member_id,
                        "name": owners[row.assignee_member_id],
                    }
                    if row.assignee_member_id
                    else None,
                    "team": {"id": row.team_id, "name": teams[row.team_id].name}
                    if row.team_id
                    else None,
                    "unread": row.id in unread_ids,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "last_message_at": row.last_message_at,
                    "target_status": clock(
                        cycle.opened_at,
                        instant,
                        cycle.target_seconds,
                        cycle.paused_seconds,
                        cycle.pause_started_at,
                        cycle.resolved_at,
                    ),
                }
            )
        )
    return result


def detail(uow: UnitOfWork, row: Case) -> CaseDetail:
    summary = staff_summaries(uow, [row])[0]
    _, definition = published(uow.session, row.config_version_id)
    cycles = list(
        uow.session.scalars(
            select(CaseCycle).where(CaseCycle.case_id == row.id).order_by(CaseCycle.cycle_number)
        )
    )
    current = next(item for item in cycles if item.cycle_number == row.current_cycle_number)
    return CaseDetail.model_validate(
        {
            **summary.model_dump(),
            "config_version_id": row.config_version_id,
            "source": row.source,
            "custom_values": row.custom_values,
            "field_definitions": definition.fields,
            "first_response_at": row.first_response_at,
            "first_response_target_at": row.created_at
            + timedelta(seconds=row.first_response_target_seconds),
            "first_response_status": clock(
                row.created_at,
                now(),
                row.first_response_target_seconds,
                finished_at=row.first_response_at,
            ),
            "current_cycle": cycle_view(current),
            "cycles": [cycle_view(item) for item in cycles],
            "related_case_id": row.related_case_id,
        }
    )


def portal_summary(uow: UnitOfWork, row: Case) -> PortalCaseSummary:
    with case_storage(uow):
        _, definition = published(uow.session, row.config_version_id)
        return PortalCaseSummary.model_validate(
            {
                "id": row.id,
                "number": row.number,
                "version": row.version,
                "subject": row.subject,
                "category_label": next(
                    item.label for item in definition.categories if item.key == row.category_key
                ),
                "state": row.state,
                "state_label": definition.state_labels[cast(State, row.state)],
                "created_at": row.created_at,
            }
        )


def portal_detail(uow: UnitOfWork, row: Case) -> PortalCaseDetail:
    with case_storage(uow):
        _, definition = published(uow.session, row.config_version_id)
        visible_fields = public_config(definition).fields
        resolution = uow.session.scalar(
            select(Message.body)
            .where(
                Message.case_id == row.id,
                Message.visibility == "public",
                Message.message_kind == "resolution",
            )
            .order_by(Message.sequence.desc())
            .limit(1)
        )
        return PortalCaseDetail(
            **portal_summary(uow, row).model_dump(),
            custom_values=cast(
                dict[str, JsonValue],
                {field.key: row.custom_values.get(field.key) for field in visible_fields},
            ),
            field_definitions=visible_fields,
            latest_public_resolution=resolution,
            current_cycle_number=row.current_cycle_number,
            related_case_id=row.related_case_id,
            can_reply=row.state in {"new", "open", "pending_customer"},
            can_reopen=row.state == "resolved",
            can_rate=row.state == "resolved"
            and uow.session.scalar(
                select(Feedback.id).where(
                    Feedback.case_id == row.id, Feedback.cycle_number == row.current_cycle_number
                )
            )
            is None,
        )


def message_view(uow: UnitOfWork, row: Message, version: int) -> MessageView:
    if uow.scope.audience == "portal":
        author = "You" if row.author_kind == "contact" else "Support team"
    else:
        author = (
            uow.session.scalar(select(User.display_name).where(User.id == row.author_user_id))
            or "System"
        )
    return MessageView(
        id=row.id,
        sequence=row.sequence,
        body=row.body,
        author_display=author,
        author_kind=row.author_kind,
        visibility=row.visibility,
        message_kind=row.message_kind,
        created_at=row.created_at,
        updated_case_version=version,
    )


def list_messages(
    uow: UnitOfWork, row: Case, filters: MessageFilters
) -> tuple[list[MessageView], str | None]:
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "audience": uow.scope.audience,
        "contact": str(uow.scope.contact_id),
        "resource": f"messages:{row.id}",
        "after_sequence": filters.after_sequence,
    }
    after = filters.after_sequence
    if filters.cursor:
        try:
            after = int(read_cursor(filters.cursor, binding)[0])
        except (ValueError, TypeError, IndexError):
            raise Fault(400, "invalid_cursor", "Return to the first message page.") from None
    query = select(Message).where(Message.case_id == row.id, Message.sequence > after)
    if uow.scope.audience == "portal":
        query = query.where(Message.visibility == "public")
    rows = list(uow.session.scalars(query.order_by(Message.sequence).limit(filters.limit + 1)))
    more = len(rows) > filters.limit
    rows = rows[: filters.limit]
    cursor = sign_cursor(binding, [str(rows[-1].sequence)]) if more else None
    return [message_view(uow, item, row.version) for item in rows], cursor


def page_cases(
    uow: UnitOfWork, filters: ListFilters | PortalFilters
) -> tuple[list[Case], str | None]:
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "audience": uow.scope.audience,
        "contact": str(uow.scope.contact_id),
        "resource": "cases",
        **filters.model_dump(mode="json", exclude={"cursor", "limit"}),
    }
    query = select(Case)
    if uow.scope.audience == "portal":
        query = query.where(Case.requester_contact_id == uow.scope.contact_id)
    if filters.q:
        pattern = (
            "%" + filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        query = query.where(
            Case.subject.ilike(pattern) | sql_cast(Case.number, String).ilike(pattern)
        )
    if filters.state:
        query = query.where(Case.state.in_(filters.state.split(",")))
    sort = "created_at"
    ranking = sql_case({"urgent": 0, "high": 1, "normal": 2, "low": 3}, value=Case.priority)
    if isinstance(filters, ListFilters):
        sort = filters.sort
        for field, column in (("priority", Case.priority), ("category", Case.category_key)):
            value = getattr(filters, field)
            if value:
                query = query.where(column.in_(value.split(",")))
        for identifier_value, identifier_column in (
            (filters.customer_id, Case.customer_id),
            (filters.assignee_id, Case.assignee_member_id),
            (filters.team_id, Case.team_id),
        ):
            if identifier_value:
                query = query.where(identifier_column == identifier_value)
        if filters.view == "unassigned":
            query = query.where(Case.state == "new", Case.assignee_member_id.is_(None))
        elif filters.view == "mine":
            query = query.where(
                Case.assignee_member_id == uow.scope.member_id,
                Case.state.in_(["new", "open", "pending_customer"]),
            )
        elif filters.view == "awaiting_customer":
            query = query.where(Case.state == "pending_customer")
        if filters.overdue is not None or filters.view == "recently_resolved":
            query = query.join(
                CaseCycle,
                (CaseCycle.case_id == Case.id)
                & (CaseCycle.cycle_number == Case.current_cycle_number),
            )
            if filters.view == "recently_resolved":
                query = query.where(
                    Case.state == "resolved", CaseCycle.resolved_at >= now() - timedelta(days=7)
                )
            if filters.overdue is not None:
                elapsed = (
                    func.extract("epoch", now() - CaseCycle.opened_at)
                    - CaseCycle.paused_seconds
                    - sql_case(
                        (
                            CaseCycle.pause_started_at.is_not(None),
                            func.extract("epoch", now() - CaseCycle.pause_started_at),
                        ),
                        else_=0,
                    )
                )
                overdue = CaseCycle.resolved_at.is_(None) & (elapsed > CaseCycle.target_seconds)
                query = query.where(overdue if filters.overdue else ~overdue)
        if filters.unread is not None:
            condition = unread_query(uow)
            query = query.where(condition if filters.unread else ~condition)
    stamp_column = Case.last_message_at if sort == "last_message_at" else Case.created_at
    if filters.cursor:
        try:
            parts = read_cursor(filters.cursor, binding)
            stamp, identifier = datetime.fromisoformat(parts[-2]), UUID(parts[-1])
            before = tuple_(stamp_column, Case.id) < tuple_(literal(stamp), literal(identifier))
            query = query.where(
                or_(ranking > int(parts[0]), (ranking == int(parts[0])) & before)
                if sort == "priority"
                else before
            )
        except (ValueError, TypeError, IndexError):
            raise Fault(400, "invalid_cursor", "Return to the first case page.") from None
    if sort == "priority":
        query = query.order_by(ranking)
    rows = list(
        uow.session.scalars(
            query.order_by(stamp_column.desc(), Case.id.desc()).limit(filters.limit + 1)
        )
    )
    more = len(rows) > filters.limit
    rows = rows[: filters.limit]
    cursor = None
    if more:
        last = rows[-1]
        parts = [
            getattr(
                last, "last_message_at" if sort == "last_message_at" else "created_at"
            ).isoformat(),
            str(last.id),
        ]
        if sort == "priority":
            parts.insert(0, str({"urgent": 0, "high": 1, "normal": 2, "low": 3}[last.priority]))
        cursor = sign_cursor(binding, parts)
    return rows, cursor
