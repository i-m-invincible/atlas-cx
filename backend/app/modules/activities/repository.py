"""Customer activity projections constrained by a verified staff scope."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select, text, tuple_

from app.modules.activities.models import CustomerEvent, EventDefinition
from app.modules.activities.schemas import EventFilters, EventView, TimelineEntry, TimelineFilters
from app.modules.customers.repository import customer
from app.platform.auth import UnitOfWork
from app.platform.protocol import Fault, missing, read_cursor, sign_cursor


def event_view(event: CustomerEvent, definition: EventDefinition) -> EventView:
    return EventView.model_validate(
        {
            "id": event.id,
            "external_event_id": event.external_event_id,
            "event_name": definition.key,
            "event_label": definition.label,
            "occurred_at": event.occurred_at,
            "received_at": event.received_at,
            "properties": event.safe_properties,
            "counts_as_activity": event.activity_flag_snapshot,
        }
    )


def event_query(
    workspace_id: UUID, customer_id: UUID
) -> Select[tuple[CustomerEvent, EventDefinition]]:
    return (
        select(CustomerEvent, EventDefinition)
        .join(
            EventDefinition,
            (EventDefinition.workspace_id == CustomerEvent.workspace_id)
            & (EventDefinition.id == CustomerEvent.event_definition_id),
        )
        .where(CustomerEvent.workspace_id == workspace_id, CustomerEvent.customer_id == customer_id)
    )


def events(
    uow: UnitOfWork, customer_id: UUID, filters: EventFilters
) -> tuple[list[EventView], str | None]:
    customer(uow.session, customer_id)
    workspace = uow.scope.workspace_id
    binding = {
        "workspace": str(workspace),
        "customer": str(customer_id),
        "list": "events",
        **filters.model_dump(mode="json", exclude={"cursor", "limit"}),
    }
    query = event_query(workspace, customer_id)
    if filters.event_name:
        query = query.where(EventDefinition.key == filters.event_name)
    if filters.from_:
        query = query.where(CustomerEvent.occurred_at >= filters.from_)
    if filters.to:
        query = query.where(CustomerEvent.occurred_at < filters.to)
    if filters.cursor:
        try:
            occurred, identifier = read_cursor(filters.cursor, binding)
            query = query.where(
                tuple_(CustomerEvent.occurred_at, CustomerEvent.id)
                < (datetime.fromisoformat(occurred), UUID(identifier))
            )
        except ValueError:
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    rows = [
        event_view(event, definition)
        for event, definition in uow.session.execute(
            query.order_by(CustomerEvent.occurred_at.desc(), CustomerEvent.id.desc()).limit(
                filters.limit + 1
            )
        )
    ]
    cursor = None
    if len(rows) > filters.limit:
        last = rows[filters.limit - 1]
        cursor = sign_cursor(binding, [last.occurred_at.isoformat(), str(last.id)])
    return rows[: filters.limit], cursor


def event_detail(uow: UnitOfWork, customer_id: UUID, event_id: UUID) -> EventView:
    customer(uow.session, customer_id)
    row = uow.session.execute(
        event_query(uow.scope.workspace_id, customer_id).where(CustomerEvent.id == event_id)
    ).one_or_none()
    if not row:
        raise missing()
    return event_view(*row)


TIMELINE = text("""
    WITH customer_cases AS (
        SELECT id, workspace_id, number, subject FROM cases
        WHERE workspace_id = :workspace AND customer_id = :customer
    ), entries AS (
        SELECT m.id, 'message' AS kind, m.created_at AS occurred_at,
            CAST(NULL AS timestamptz) AS received_at, c.id AS reference_id,
            concat('Case #', c.number, ' · ', CASE WHEN m.visibility = 'internal'
                THEN 'Internal note' ELSE 'Message' END) AS title,
            left(m.body, 160) AS preview,
            coalesce(u.display_name, initcap(m.author_kind)) AS actor
        FROM customer_cases c JOIN messages m
            ON (m.workspace_id, m.case_id) = (c.workspace_id, c.id)
        LEFT JOIN users u ON u.id = m.author_user_id
        UNION ALL
        SELECT t.id, 'transition', t.occurred_at, NULL, c.id,
            concat('Case #', c.number, ' · ', initcap(replace(t.to_state, '_', ' '))),
            left(coalesce(t.reason, c.subject), 160), coalesce(u.display_name, 'Service')
        FROM customer_cases c JOIN case_transitions t
            ON (t.workspace_id, t.case_id) = (c.workspace_id, c.id)
        LEFT JOIN users u ON u.id = t.actor_user_id
        UNION ALL
        SELECT e.id, 'event', e.occurred_at, e.received_at, e.id, d.label,
            d.key, 'Event ingestion'
        FROM customer_events e JOIN event_definitions d
            ON (d.workspace_id, d.id) = (e.workspace_id, e.event_definition_id)
        WHERE e.workspace_id = :workspace AND e.customer_id = :customer
        UNION ALL
        SELECT t.id, 'task', t.created_at, NULL, t.id, 'Follow-up created',
            left(t.title, 160), coalesce(u.display_name, 'Service')
        FROM tasks t LEFT JOIN memberships m
            ON (m.workspace_id, m.id) = (t.workspace_id, t.created_by_member_id)
        LEFT JOIN users u ON u.id = m.user_id
        WHERE t.workspace_id = :workspace AND t.customer_id = :customer
        UNION ALL
        SELECT a.id, 'task', a.occurred_at, NULL, t.id,
            CASE a.action WHEN 'task.completed' THEN 'Follow-up completed'
                WHEN 'task.reopened' THEN 'Follow-up reopened' ELSE 'Follow-up cancelled' END,
            left(t.title, 160), coalesce(u.display_name, 'Service')
        FROM tasks t JOIN audit_events a
            ON (a.workspace_id, a.entity_id) = (t.workspace_id, t.id)
            AND a.entity_type = 'task'
        LEFT JOIN users u ON u.id = a.actor_user_id
        WHERE t.workspace_id = :workspace AND t.customer_id = :customer
            AND a.action IN ('task.completed', 'task.reopened', 'task.cancelled')
        UNION ALL
        SELECT f.id, 'feedback', f.created_at, NULL, c.id,
            concat('Case #', c.number, ' · Feedback'), concat(f.rating, ' / 5'),
            'Requester'
        FROM customer_cases c JOIN feedback f
            ON (f.workspace_id, f.case_id) = (c.workspace_id, c.id)
    )
    SELECT * FROM entries
    WHERE kind = ANY(CAST(:kinds AS text[]))
      AND (CAST(:cursor_time AS timestamptz) IS NULL OR (occurred_at, kind, id)
           < (CAST(:cursor_time AS timestamptz), :cursor_kind, CAST(:cursor_id AS uuid)))
    ORDER BY occurred_at DESC, kind DESC, id DESC
    LIMIT :limit
""")


def timeline(
    uow: UnitOfWork, customer_id: UUID, filters: TimelineFilters
) -> tuple[list[TimelineEntry], str | None]:
    customer(uow.session, customer_id)
    kinds = (
        sorted(set(filters.kinds.split(",")))
        if filters.kinds
        else [
            "message",
            "transition",
            "event",
            "task",
            "feedback",
        ]
    )
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "customer": str(customer_id),
        "list": "timeline",
        "kinds": kinds,
    }
    cursor_time, cursor_kind, cursor_id = None, None, None
    if filters.cursor:
        try:
            cursor_time, cursor_kind, cursor_id = read_cursor(filters.cursor, binding)
        except ValueError:
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    rows = [
        TimelineEntry.model_validate(row)
        for row in uow.session.execute(
            TIMELINE,
            {
                "workspace": uow.scope.workspace_id,
                "customer": customer_id,
                "kinds": kinds,
                "cursor_time": cursor_time,
                "cursor_kind": cursor_kind,
                "cursor_id": cursor_id,
                "limit": filters.limit + 1,
            },
        ).mappings()
    ]
    cursor = None
    if len(rows) > filters.limit:
        last = rows[filters.limit - 1]
        cursor = sign_cursor(binding, [last.occurred_at.isoformat(), last.kind, str(last.id)])
    return rows[: filters.limit], cursor
