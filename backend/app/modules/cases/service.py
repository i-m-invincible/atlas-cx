from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from fastapi import Request
from pydantic import JsonValue
from sqlalchemy import select

from app.modules.cases import repository as repo
from app.modules.cases.clocks import ALLOWED, DESTINATION
from app.modules.cases.models import (
    Case,
    CaseCycle,
    CaseTransition,
    Message,
    ReadMarker,
    WorkspaceCounter,
)
from app.modules.cases.schemas import (
    CaseCreatePortal,
    CaseCreateStaff,
    CasePatch,
    Definition,
    MessageCreate,
    PortalMessageCreate,
    Priority,
    ReadInput,
    ReopenInput,
    TransitionInput,
)
from app.modules.customers.models import Contact, Customer
from app.modules.identity.models import Membership
from app.modules.workspace.case_configuration import published
from app.modules.workspace.models import Workspace
from app.modules.workspace.team_models import Team, TeamMember
from app.platform import idempotency
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role
from app.platform.protocol import Fault, match_version, missing, now


def authorize_write(uow: UnitOfWork) -> None:
    if uow.scope.audience == "staff":
        require_role(uow.scope, "admin", "manager", "agent")


def instant_for(row: Case) -> datetime:
    instant = now()
    if instant < row.updated_at:
        raise Fault(
            503, "clock_unavailable", "The service clock is unavailable. Try again shortly."
        )
    return instant


def validate_assignment(
    uow: UnitOfWork, member_id: UUID | None, team_id: UUID | None, required: bool = False
) -> None:
    if team_id:
        team = uow.session.get(Team, team_id)
        if not team or team.archived_at:
            raise Fault(422, "invalid_team", "Choose an active team in this workspace.")
    if member_id is None:
        if required:
            raise Fault(
                409, "assignment_required", "Assign an active staff member before continuing."
            )
        return
    member = uow.session.get(Membership, member_id)
    if not member or not member.active or member.role not in {"admin", "manager", "agent"}:
        raise Fault(422, "invalid_assignee", "Choose an active staff member who can handle cases.")
    if team_id and not uow.session.get(TeamMember, (uow.scope.workspace_id, team_id, member_id)):
        raise Fault(
            422, "team_membership_required", "The assignee must belong to the selected team."
        )


def values_for(
    definition: Definition,
    supplied: dict[str, JsonValue],
    *,
    existing: dict[str, object] | None = None,
    portal: bool = False,
    resolving: bool = False,
) -> dict[str, object]:
    fields = {field.key: field for field in definition.fields}
    if set(supplied) - fields.keys():
        raise Fault(422, "invalid_custom_values", "Remove unknown case fields.")
    values = dict(existing or {})
    for key, field in fields.items():
        if key in supplied:
            if portal and not (field.portal_visible and field.portal_editable_on_create):
                raise Fault(
                    422, "invalid_custom_values", "Only the visible request fields may be supplied."
                )
            values[key] = supplied[key]
        elif existing is None:
            values[key] = field.default
        value = values.get(key)
        required = field.required_on_resolve if resolving else field.required_on_create
        if value is None:
            if required:
                raise Fault(
                    422, "required_case_field", f"Complete the required field: {field.label}."
                )
            continue
        valid = False
        if field.type in {"string", "single_select"}:
            valid = isinstance(value, str) and 1 <= len(value.strip()) <= 4000
            if field.type == "single_select":
                valid = valid and value in field.allowed_values
        elif field.type == "boolean":
            valid = isinstance(value, bool)
        elif field.type in {"integer", "decimal"}:
            valid = isinstance(value, (int, float)) and not isinstance(value, bool)
            if field.type == "integer":
                valid = valid and isinstance(value, int)
            if valid:
                try:
                    number = Decimal(str(value))
                    valid = (
                        number.is_finite()
                        and (field.minimum is None or number >= Decimal(str(field.minimum)))
                        and (field.maximum is None or number <= Decimal(str(field.maximum)))
                    )
                except InvalidOperation:
                    valid = False
        elif field.type == "date" and isinstance(value, str):
            try:
                valid = date.fromisoformat(value).isoformat() == value
            except ValueError:
                valid = False
        if not valid:
            raise Fault(422, "invalid_custom_values", f"Review the field: {field.label}.")
    return values


def category(definition: Definition, key: str) -> UUID | None:
    item = next((item for item in definition.categories if item.key == key), None)
    if not item:
        raise Fault(422, "invalid_category", "Choose a category from this case’s configuration.")
    return item.default_team_id


def audit(uow: UnitOfWork, row: Case, request: Request, action: str, fields: list[str]) -> None:
    record_audit(
        uow.session,
        row.workspace_id,
        uow.scope.user_id,
        action,
        "case",
        row.id,
        fields,
        request.state.request_id,
        actor_kind=uow.scope.audience,
    )


def advance_marker(uow: UnitOfWork, row: Case, sequence: int) -> int:
    if uow.scope.audience != "staff" or uow.scope.member_id is None:
        return sequence
    marker = uow.session.scalar(
        select(ReadMarker).where(
            ReadMarker.case_id == row.id, ReadMarker.member_id == uow.scope.member_id
        )
    )
    if not marker:
        marker = ReadMarker(
            workspace_id=row.workspace_id,
            case_id=row.id,
            member_id=uow.scope.member_id,
            last_read_sequence=sequence,
        )
        uow.session.add(marker)
    else:
        marker.last_read_sequence = max(marker.last_read_sequence, sequence)
        marker.updated_at = now()
    return marker.last_read_sequence


def append(
    uow: UnitOfWork, row: Case, body: str, kind: str, instant: datetime, visibility: str = "public"
) -> Message:
    author_kind = "staff" if uow.scope.audience == "staff" else "contact"
    message = Message(
        workspace_id=row.workspace_id,
        case_id=row.id,
        author_user_id=uow.scope.user_id,
        author_kind=author_kind,
        visibility=visibility,
        message_kind=kind,
        body=body,
        created_at=instant,
        updated_case_version=row.version,
    )
    uow.session.add(message)
    uow.session.flush()
    row.last_message_at = instant
    if visibility == "public":
        row.last_public_message_seq = message.sequence
    if (
        visibility == "public"
        and author_kind == "staff"
        and kind in {"reply", "info_request", "resolution"}
        and row.first_response_at is None
    ):
        row.first_response_at = instant
    advance_marker(uow, row, message.sequence)
    return message


def settle_pause(cycle: CaseCycle, instant: datetime) -> None:
    if cycle.pause_started_at:
        if instant < cycle.pause_started_at:
            raise Fault(503, "clock_unavailable", "The service clock is unavailable.")
        cycle.paused_seconds += (instant - cycle.pause_started_at).total_seconds()
        cycle.pause_started_at = None


def change_state(
    uow: UnitOfWork, row: Case, destination: str, instant: datetime, reason: str | None = None
) -> CaseTransition:
    transition = CaseTransition(
        workspace_id=row.workspace_id,
        case_id=row.id,
        cycle_number=row.current_cycle_number,
        from_state=row.state,
        to_state=destination,
        actor_user_id=uow.scope.user_id,
        occurred_at=instant,
        reason=reason,
    )
    row.state = destination
    return transition


def create(uow: UnitOfWork, payload: CaseCreateStaff | CaseCreatePortal, request: Request) -> Case:
    authorize_write(uow)
    # This contact lookup happens under the original portal RLS scope.
    contact_id = (
        payload.requester_contact_id
        if isinstance(payload, CaseCreateStaff)
        else uow.scope.contact_id
    )
    contact = uow.session.scalar(select(Contact).where(Contact.id == contact_id))
    if not contact:
        raise missing()
    with repo.case_storage(uow):
        customer = uow.session.get(Customer, contact.customer_id)
        if not customer:
            raise missing()
        if isinstance(payload, CaseCreateStaff) and customer.id != payload.customer_id:
            raise Fault(422, "requester_mismatch", "Choose a contact belonging to this customer.")
        replay, exists = idempotency.prepare(uow, request, payload)
        if exists:
            assert replay.resource_id
            return repo.get_case(uow, replay.resource_id)
        if customer.archived_at or contact.archived_at:
            raise Fault(409, "archived", "Archived customer records cannot receive new requests.")
        workspace = uow.session.get(Workspace, uow.scope.workspace_id)
        assert workspace
        config, definition = published(uow.session, workspace.active_case_config_id)
        team_id = category(definition, payload.category_key)
        assignee = None
        priority = "normal"
        source = "portal"
        if isinstance(payload, CaseCreateStaff):
            team_id = payload.team_id if "team_id" in payload.model_fields_set else team_id
            assignee, priority, source = (
                payload.assignee_member_id,
                payload.priority,
                payload.source,
            )
        validate_assignment(uow, assignee, team_id)
        if payload.related_case_id:
            repo.get_case(uow, payload.related_case_id)
        custom = values_for(
            definition, payload.custom_values, portal=uow.scope.audience == "portal"
        )
        counter = uow.session.get(WorkspaceCounter, workspace.id, with_for_update=True)
        if not counter:
            raise Fault(503, "configuration_unavailable", "Case numbering is not ready.")
        number = counter.next_case_number
        counter.next_case_number += 1
        instant = now()
        target = definition.priorities[cast(Priority, priority)]
        row = Case(
            workspace_id=workspace.id,
            number=number,
            customer_id=customer.id,
            requester_contact_id=contact.id,
            config_version_id=config.id,
            category_key=payload.category_key,
            subject=payload.subject,
            priority=priority,
            source=source,
            team_id=team_id,
            assignee_member_id=assignee,
            custom_values=custom,
            related_case_id=payload.related_case_id,
            first_response_target_seconds=target.response_minutes * 60,
            resolution_target_seconds=target.resolution_minutes * 60,
            created_at=instant,
            updated_at=instant,
            last_message_at=instant,
        )
        uow.session.add(row)
        uow.session.flush()
        cycle = CaseCycle(
            workspace_id=workspace.id,
            case_id=row.id,
            cycle_number=1,
            opened_at=instant,
            target_seconds=row.resolution_target_seconds,
        )
        uow.session.add(cycle)
        uow.session.flush()
        initial = append(uow, row, payload.description, "initial", instant)
        uow.session.add(
            CaseTransition(
                workspace_id=workspace.id,
                case_id=row.id,
                cycle_number=1,
                from_state=None,
                to_state="new",
                actor_user_id=uow.scope.user_id,
                message_id=initial.id,
                occurred_at=instant,
            )
        )
        audit(uow, row, request, "case.created", ["subject", "category_key", "priority", "source"])
        idempotency.complete(replay, "case", row.id, 201)
        uow.session.flush()
        return row


def patch(uow: UnitOfWork, identifier: UUID, payload: CasePatch, request: Request) -> Case:
    row = repo.get_case(uow, identifier, True)
    require_role(uow.scope, "admin", "manager", "agent")
    match_version(request, row.version)
    if row.state == "closed":
        raise Fault(409, "case_closed", "Closed cases cannot be changed. Create a related case.")
    _, definition = published(uow.session, row.config_version_id)
    changes = payload.model_dump(exclude_unset=True)
    if payload.category_key:
        category(definition, payload.category_key)
    member = (
        payload.assignee_member_id if "assignee_member_id" in changes else row.assignee_member_id
    )
    team = payload.team_id if "team_id" in changes else row.team_id
    validate_assignment(uow, member, team, row.state != "new")
    if payload.custom_values is not None:
        changes["custom_values"] = values_for(
            definition, payload.custom_values, existing=row.custom_values
        )
    for key, value in changes.items():
        setattr(row, key, value)
    row.version += 1
    row.updated_at = instant_for(row)
    audit(uow, row, request, "case.updated", list(changes))
    uow.session.flush()
    return row


def post_message(
    uow: UnitOfWork,
    identifier: UUID,
    payload: MessageCreate | PortalMessageCreate,
    request: Request,
) -> tuple[Case, Message]:
    row = repo.get_case(uow, identifier)
    authorize_write(uow)
    with repo.case_storage(uow):
        row = repo.get_case(uow, identifier, True)
        replay, exists = idempotency.prepare(uow, request, payload)
        if exists:
            message = uow.session.get(Message, replay.resource_id)
            if (
                not message
                or message.case_id != row.id
                or (uow.scope.audience == "portal" and message.visibility != "public")
            ):
                raise missing()
            return row, message
        match_version(request, row.version)
        visibility = payload.visibility if isinstance(payload, MessageCreate) else "public"
        if row.state == "closed":
            raise Fault(409, "case_closed", "This case is closed. Create a related request.")
        if row.state == "resolved" and visibility == "public":
            raise Fault(
                409, "reopen_required", "This case is resolved. Use Reopen before posting a reply."
            )
        instant = instant_for(row)
        row.version += 1
        row.updated_at = instant
        related_event = None
        if row.state == "new" and uow.scope.audience == "staff" and visibility == "public":
            row.assignee_member_id = row.assignee_member_id or uow.scope.member_id
            validate_assignment(uow, row.assignee_member_id, row.team_id, True)
            related_event = change_state(uow, row, "open", instant)
        elif row.state == "pending_customer" and uow.scope.audience == "portal":
            settle_pause(repo.current_cycle(uow, row), instant)
            related_event = change_state(uow, row, "open", instant)
        message = append(
            uow,
            row,
            payload.body,
            "note" if visibility == "internal" else "reply",
            instant,
            visibility,
        )
        if related_event:
            related_event.message_id = message.id
            uow.session.add(related_event)
        audit(
            uow,
            row,
            request,
            "case.note_added" if visibility == "internal" else "case.reply_posted",
            ["messages"],
        )
        idempotency.complete(replay, "message", message.id)
        uow.session.flush()
        return row, message


def transition(
    uow: UnitOfWork, identifier: UUID, payload: TransitionInput | ReopenInput, request: Request
) -> tuple[Case, CaseTransition, Message | None]:
    row = repo.get_case(uow, identifier)
    authorize_write(uow)
    action = payload.action if isinstance(payload, TransitionInput) else "reopen"
    if action == "close":
        require_role(uow.scope, "admin", "manager")
    with repo.case_storage(uow):
        row = repo.get_case(uow, identifier, True)
        replay, exists = idempotency.prepare(uow, request, payload)
        if exists:
            previous = uow.session.get(CaseTransition, replay.resource_id)
            if not previous or previous.case_id != row.id:
                raise missing()
            message = uow.session.get(Message, previous.message_id) if previous.message_id else None
            return row, previous, message
        match_version(request, row.version)
        if row.state not in ALLOWED[action]:
            raise Fault(
                409, "invalid_transition", "This action is not available in the current case state."
            )
        instant = instant_for(row)
        cycle = repo.current_cycle(uow, row)
        reason = payload.reason if isinstance(payload, TransitionInput) else None
        if action == "triage":
            assert isinstance(payload, TransitionInput)
            row.assignee_member_id = payload.assignee_member_id or row.assignee_member_id
        if action in {"triage", "resolve", "reopen"}:
            validate_assignment(uow, row.assignee_member_id, row.team_id, True)
        row.version += 1
        row.updated_at = instant
        if row.state == "pending_customer":
            settle_pause(cycle, instant)
        if action == "ask_customer":
            cycle.pause_started_at = instant
        elif action == "resolve":
            assert isinstance(payload, TransitionInput)
            _, definition = published(uow.session, row.config_version_id)
            row.custom_values = values_for(
                definition, payload.custom_values or {}, existing=row.custom_values, resolving=True
            )
            if payload.related_case_id:
                if payload.related_case_id == row.id:
                    raise Fault(422, "invalid_related_case", "A case cannot be related to itself.")
                repo.get_case(uow, payload.related_case_id)
                row.related_case_id = payload.related_case_id
            if payload.resolution_code == "duplicate" and row.related_case_id is None:
                raise Fault(
                    422,
                    "related_case_required",
                    "Choose the related case for a duplicate resolution.",
                )
            cycle.resolved_at, cycle.resolved_by_member_id = instant, uow.scope.member_id
            cycle.resolution_code, cycle.resolution_summary = (
                payload.resolution_code,
                payload.resolution_summary,
            )
        elif action == "reopen":
            row.current_cycle_number += 1
            uow.session.add(
                CaseCycle(
                    workspace_id=row.workspace_id,
                    case_id=row.id,
                    cycle_number=row.current_cycle_number,
                    opened_at=instant,
                    target_seconds=row.resolution_target_seconds,
                )
            )
            uow.session.flush()
        event = change_state(uow, row, DESTINATION[action], instant, reason)
        message = None
        if action in {"ask_customer", "resolve"}:
            assert isinstance(payload, TransitionInput)
            body = payload.message if action == "ask_customer" else payload.resolution_summary
            assert body
            message = append(
                uow,
                row,
                body,
                "info_request" if action == "ask_customer" else "resolution",
                instant,
            )
        elif isinstance(payload, ReopenInput):
            message = append(uow, row, payload.message, "reopen", instant)
        if message:
            event.message_id = message.id
        uow.session.add(event)
        audit(
            uow,
            row,
            request,
            "case." + action,
            ["state", "current_cycle_number"] if action == "reopen" else ["state"],
        )
        uow.session.flush()
        idempotency.complete(replay, "transition", event.id)
        uow.session.flush()
        return row, event, message


def mark_read(uow: UnitOfWork, identifier: UUID, payload: ReadInput) -> int:
    row = repo.get_case(uow, identifier)
    require_role(uow.scope, "admin", "manager", "agent", "viewer")
    if payload.last_read_sequence:
        visible = uow.session.scalar(
            select(Message.id).where(
                Message.case_id == row.id, Message.sequence == payload.last_read_sequence
            )
        )
        if not visible:
            raise Fault(
                422,
                "invalid_read_marker",
                "Read markers must refer to a visible message in this case.",
            )
    return advance_marker(uow, row, payload.last_read_sequence)
