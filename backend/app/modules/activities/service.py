import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.activities.models import CustomerEvent, EventDefinition
from app.modules.activities.schemas import EventBatch, EventInput, IngestResult, PropertyRule
from app.modules.customers.models import Customer
from app.modules.identity.security import digest
from app.modules.workspace.credential_models import ApiCredential
from app.modules.workspace.models import Workspace
from app.platform.config import get_settings
from app.platform.database import set_scope
from app.platform.protocol import Fault, now
from app.platform.rate_limits import RateBucket

MAX_BODY_BYTES = 1024 * 1024
MAX_PROPERTY_BYTES = 8192


def canonical(data: object) -> bytes:
    try:
        return json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (UnicodeError, ValueError):
        raise Fault(422, "invalid_event", "Use finite numbers and valid UTF-8 text.") from None


def event_hash(event: EventInput) -> str:
    return hashlib.sha256(
        canonical(
            {
                "customer_external_id": event.customer_external_id,
                "event_name": event.event_name,
                "occurred_at": event.occurred_at.astimezone(UTC).isoformat(),
                "properties": event.properties,
            }
        )
    ).hexdigest()


def validate_properties(event: EventInput, rules: dict[str, PropertyRule]) -> None:
    for key, value in event.properties.items():
        rule = rules.get(key)
        if not rule:
            raise Fault(422, "unregistered_property", "Remove unregistered event properties.")
        valid = {
            "string": isinstance(value, str)
            and "\x00" not in value
            and len(value) <= (rule.max_length or 0),
            "integer": type(value) is int,
            "number": type(value) is int or (isinstance(value, float) and math.isfinite(value)),
            "boolean": isinstance(value, bool),
        }[rule.type]
        if not valid:
            raise Fault(422, "invalid_property", f"Check the type and length of property {key}.")


def invalid_credential() -> Fault:
    return Fault(
        401,
        "invalid_ingestion_credential",
        "Use a valid event ingestion credential.",
        {"WWW-Authenticate": "Bearer"},
    )


def authenticate_ingestion(session: Session, token: str) -> ApiCredential:
    if not token.startswith("atlas_ev_") or len(token) != 52:
        raise invalid_credential()
    session.execute(
        text("SELECT set_config('app.credential_hash', :value, true)"), {"value": digest(token)}
    )
    row = session.scalar(select(ApiCredential).where(ApiCredential.token_hash == digest(token)))
    session.execute(text("SELECT set_config('app.credential_hash', '', true)"))
    if not row or row.revoked_at:
        raise invalid_credential()
    identifier, workspace_id = row.id, row.workspace_id
    set_scope(session, workspace_id, "ingest")
    session.execute(
        text("SELECT set_config('app.ingest_credential', :value, true)"), {"value": str(identifier)}
    )
    # Serialize with customer changes, definition edits, revocation and competing batches.
    workspace = session.get(Workspace, workspace_id, with_for_update={"key_share": True})
    row = session.get(ApiCredential, identifier, populate_existing=True, with_for_update=True)
    if (
        not workspace
        or workspace.archived_at
        or not row
        or row.revoked_at
        or row.scope != "events:write"
    ):
        raise invalid_credential()
    return row


def consume_batch(session: Session, credential: ApiCredential, instant: datetime) -> None:
    principal = str(credential.id)
    start = instant.replace(second=0, microsecond=0)
    session.execute(
        delete(RateBucket).where(
            RateBucket.principal_key == principal,
            RateBucket.operation == "events.batch",
            RateBucket.window_start < start,
        )
    )
    statement = insert(RateBucket).values(
        workspace_id=credential.workspace_id,
        principal_key=principal,
        operation="events.batch",
        window_start=start,
        request_count=1,
    )
    count = session.scalar(
        statement.on_conflict_do_update(
            index_elements=["workspace_id", "principal_key", "operation", "window_start"],
            set_={"request_count": RateBucket.request_count + 1},
        ).returning(RateBucket.request_count)
    )
    if count is not None and count > get_settings().event_batches_per_minute:
        raise Fault(
            429,
            "rate_limited",
            "Too many event batches. Try again shortly.",
            {"Retry-After": str(60 - instant.second)},
        )


def ingest(
    session: Session, credential: ApiCredential, batch: EventBatch, instant: datetime
) -> IngestResult:
    existing = {
        row.external_event_id: row
        for row in session.scalars(
            select(CustomerEvent).where(
                CustomerEvent.external_event_id.in_(
                    {event.external_event_id for event in batch.events}
                )
            )
        )
    }
    customers = {
        row.external_id: row
        for row in session.scalars(
            select(Customer).where(
                Customer.external_id.in_({event.customer_external_id for event in batch.events}),
                Customer.lifecycle == "active",
                Customer.archived_at.is_(None),
            )
        )
    }
    definitions = {
        row.key: row
        for row in session.scalars(
            select(EventDefinition).where(
                EventDefinition.key.in_({event.event_name for event in batch.events}),
                EventDefinition.enabled.is_(True),
            )
        )
    }
    rules = {
        key: {
            name: PropertyRule.model_validate(rule)
            for name, rule in row.allowed_properties_json.items()
        }
        for key, row in definitions.items()
    }
    ids: list[UUID] = []
    inserted = 0
    for event in batch.events:
        if len(canonical(event.properties)) > MAX_PROPERTY_BYTES:
            raise Fault(
                413, "event_properties_too_large", "Event properties must fit within 8 KiB."
            )
        payload_hash = event_hash(event)
        prior = existing.get(event.external_event_id)
        if prior:
            if prior.payload_hash != payload_hash:
                raise Fault(
                    409, "event_conflict", "An event ID was already used with different content."
                )
            ids.append(prior.id)
            continue
        if event.occurred_at > instant + timedelta(
            minutes=5
        ) or event.occurred_at < instant - timedelta(days=90):
            raise Fault(
                422,
                "event_time_out_of_range",
                "Use an occurrence time within the permitted 90-day and five-minute limits.",
            )
        customer = customers.get(event.customer_external_id)
        definition = definitions.get(event.event_name)
        if not customer:
            raise Fault(422, "unknown_event_customer", "Use an active customer external ID.")
        if not definition:
            raise Fault(422, "unregistered_event", "Use an enabled event definition.")
        validate_properties(event, rules[event.event_name])
        row = CustomerEvent(
            id=uuid4(),
            workspace_id=credential.workspace_id,
            customer_id=customer.id,
            event_definition_id=definition.id,
            external_event_id=event.external_event_id,
            occurred_at=event.occurred_at.astimezone(UTC),
            received_at=instant,
            safe_properties=event.properties,
            payload_hash=payload_hash,
            activity_flag_snapshot=definition.counts_as_activity,
        )
        session.add(row)
        existing[row.external_event_id] = row
        ids.append(row.id)
        inserted += 1
    credential.last_used_at = instant
    session.flush()
    return IngestResult(
        received_count=len(ids),
        inserted_count=inserted,
        duplicate_count=len(ids) - inserted,
        ids=ids,
    )


def ingest_batch(session: Session, token: str, batch: EventBatch) -> IngestResult | Fault:
    credential = authenticate_ingestion(session, token)
    instant = now()
    consume_batch(session, credential, instant)
    try:
        with session.begin_nested():
            return ingest(session, credential, batch, instant)
    except Fault as fault:
        return fault
