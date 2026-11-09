from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue, model_validator

from app.platform.protocol import Input

State = Literal["new", "open", "pending_customer", "resolved", "closed"]
Priority = Literal["urgent", "high", "normal", "low"]
ResolutionCode = Literal["answered", "fixed", "fulfilled", "declined", "duplicate", "other"]


class Category(Input):
    key: str = Field(pattern=r"^[a-z0-9_]{1,50}$")
    label: str = Field(min_length=1, max_length=120)
    default_team_id: UUID | None = None


class Targets(Input):
    response_minutes: int = Field(gt=0, le=35_791_394, strict=True)
    resolution_minutes: int = Field(gt=0, le=35_791_394, strict=True)


class FieldDefinition(Input):
    key: str = Field(pattern=r"^[a-z0-9_]{1,50}$")
    label: str = Field(min_length=1, max_length=120)
    type: Literal["string", "integer", "decimal", "boolean", "date", "single_select"]
    required_on_create: bool = False
    required_on_resolve: bool = False
    portal_visible: bool = False
    portal_editable_on_create: bool = False
    allowed_values: list[Annotated[str, Field(min_length=1, max_length=4000)]] = Field(
        default_factory=list, max_length=50
    )
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)
    default: JsonValue = None


class Definition(Input):
    categories: list[Category] = Field(min_length=1, max_length=50)
    state_labels: dict[State, Annotated[str, Field(min_length=1, max_length=120)]]
    priorities: dict[Priority, Targets]
    fields: list[FieldDefinition] = Field(default_factory=list, max_length=20)
    portal_default_priority: Literal["normal"] = "normal"

    @model_validator(mode="after")
    def complete(self) -> "Definition":
        if set(self.state_labels) != {"new", "open", "pending_customer", "resolved", "closed"}:
            raise ValueError("All semantic state labels are required")
        if set(self.priorities) != {"urgent", "high", "normal", "low"}:
            raise ValueError("All priority targets are required")
        if len({item.key for item in self.categories}) != len(self.categories):
            raise ValueError("Category keys must be unique")
        if len({item.key for item in self.fields}) != len(self.fields):
            raise ValueError("Field keys must be unique")
        return self


def valid_field_value(field: FieldDefinition, value: object) -> bool:
    if field.type in {"string", "single_select"}:
        return (
            isinstance(value, str)
            and 1 <= len(value.strip()) <= 4000
            and (field.type == "string" or value in field.allowed_values)
        )
    if field.type == "boolean":
        return isinstance(value, bool)
    if field.type in {"integer", "decimal"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if field.type == "integer" and not isinstance(value, int):
            return False
        try:
            number = Decimal(str(value))
            return (
                number.is_finite()
                and (field.minimum is None or number >= Decimal(str(field.minimum)))
                and (field.maximum is None or number <= Decimal(str(field.maximum)))
            )
        except InvalidOperation:
            return False
    if field.type == "date" and isinstance(value, str):
        try:
            return date.fromisoformat(value).isoformat() == value
        except ValueError:
            return False
    return False


class ConfigView(BaseModel):
    id: UUID
    version: int
    number: int
    status: Literal["draft", "published"]
    definition: Definition
    published_at: datetime | None


class PublicCategory(BaseModel):
    key: str
    label: str


class PublicField(BaseModel):
    key: str
    label: str
    type: str
    required_on_create: bool
    portal_editable_on_create: bool
    allowed_values: list[str]
    minimum: float | None
    maximum: float | None


class PortalConfig(BaseModel):
    categories: list[PublicCategory]
    state_labels: dict[State, str]
    fields: list[PublicField]


class CaseCreatePortal(Input):
    category_key: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    custom_values: dict[str, JsonValue] = Field(default_factory=dict, max_length=20)
    related_case_id: UUID | None = None


class CaseCreateStaff(CaseCreatePortal):
    customer_id: UUID
    requester_contact_id: UUID
    priority: Priority = "normal"
    source: Literal["manual_phone", "manual_email", "manual_other"] = "manual_other"
    team_id: UUID | None = None
    assignee_member_id: UUID | None = None


class CasePatch(Input):
    category_key: str | None = Field(default=None, min_length=1, max_length=50)
    priority: Priority | None = None
    team_id: UUID | None = None
    assignee_member_id: UUID | None = None
    custom_values: dict[str, JsonValue] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def nonempty(self) -> "CasePatch":
        if not self.model_fields_set or any(
            getattr(self, key) is None
            for key in self.model_fields_set - {"team_id", "assignee_member_id"}
        ):
            raise ValueError("Include at least one valid change")
        return self


class MessageCreate(Input):
    body: str = Field(min_length=1, max_length=10000)
    visibility: Literal["public", "internal"] = "public"


class PortalMessageCreate(Input):
    body: str = Field(min_length=1, max_length=10000)


class ReopenInput(Input):
    message: str = Field(min_length=1, max_length=4000)


class TransitionInput(Input):
    action: Literal["triage", "ask_customer", "resume", "resolve", "reopen", "close"]
    assignee_member_id: UUID | None = None
    message: str | None = Field(default=None, min_length=1, max_length=4000)
    reason: str | None = Field(default=None, min_length=1, max_length=4000)
    resolution_summary: str | None = Field(default=None, min_length=1, max_length=4000)
    resolution_code: ResolutionCode | None = None
    custom_values: dict[str, JsonValue] | None = Field(default=None, max_length=20)
    related_case_id: UUID | None = None

    @model_validator(mode="after")
    def action_fields(self) -> "TransitionInput":
        allowed = {
            "triage": {"assignee_member_id"},
            "ask_customer": {"message"},
            "resume": {"reason"},
            "resolve": {
                "resolution_summary",
                "resolution_code",
                "custom_values",
                "related_case_id",
            },
            "reopen": {"reason"},
            "close": {"reason"},
        }[self.action]
        if self.model_fields_set - allowed - {"action"}:
            raise ValueError("Only fields for this action are accepted")
        required = {
            "ask_customer": {"message"},
            "resume": {"reason"},
            "resolve": {"resolution_summary", "resolution_code"},
            "reopen": {"reason"},
            "close": {"reason"},
        }.get(self.action, set())
        if any(getattr(self, key) is None for key in required):
            raise ValueError("Complete the required action fields")
        return self


class ReadInput(Input):
    last_read_sequence: int = Field(ge=0)


class ClockView(BaseModel):
    status: Literal["due", "overdue", "paused", "met", "missed"]
    elapsed_seconds: float
    remaining_seconds: float
    target_seconds: int
    is_overdue: bool
    due_at: datetime | None


class CycleView(BaseModel):
    cycle_number: int
    opened_at: datetime
    target_seconds: int
    paused_seconds: float
    pause_started_at: datetime | None
    resolved_at: datetime | None
    resolution_code: str | None
    resolution_summary: str | None


class Reference(BaseModel):
    id: UUID
    name: str


class CaseSummary(BaseModel):
    id: UUID
    number: int
    version: int
    subject: str
    state: State
    state_label: str
    category_key: str
    category_label: str
    priority: Priority
    customer: Reference
    requester: Reference
    team: Reference | None
    assignee: Reference | None
    unread: bool
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    target_status: ClockView


class CaseDetail(CaseSummary):
    config_version_id: UUID
    source: str
    custom_values: dict[str, JsonValue]
    field_definitions: list[FieldDefinition]
    first_response_at: datetime | None
    first_response_target_at: datetime
    first_response_status: ClockView
    current_cycle: CycleView
    cycles: list[CycleView]
    related_case_id: UUID | None


class PortalCaseSummary(BaseModel):
    id: UUID
    number: int
    version: int
    subject: str
    category_label: str
    state: State
    state_label: str
    created_at: datetime


class PortalCaseDetail(PortalCaseSummary):
    custom_values: dict[str, JsonValue]
    field_definitions: list[PublicField]
    latest_public_resolution: str | None
    current_cycle_number: int
    can_reply: bool
    can_reopen: bool
    can_rate: bool = False
    related_case_id: UUID | None


class MessageView(BaseModel):
    id: UUID
    sequence: int
    body: str
    author_display: str
    author_kind: str
    visibility: str
    message_kind: str
    created_at: datetime
    updated_case_version: int


class PortalMessageView(MessageView):
    visibility: Literal["public"] = "public"


class TransitionResult(BaseModel):
    case: CaseDetail
    transition_id: UUID
    message_id: UUID | None


class HistoryView(BaseModel):
    id: UUID
    kind: Literal["transition", "audit"]
    occurred_at: datetime
    action: str
    from_state: str | None = None
    to_state: str | None = None
    cycle_number: int | None = None
    changed_fields: list[str] = Field(default_factory=list)
    reason: str | None = None


class ListFilters(Input):
    q: str = Field(default="", max_length=200)
    state: str | None = Field(default=None, max_length=150)
    priority: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=200)
    customer_id: UUID | None = None
    assignee_id: UUID | None = None
    team_id: UUID | None = None
    overdue: bool | None = None
    unread: bool | None = None
    view: Literal["all", "unassigned", "mine", "awaiting_customer", "recently_resolved"] = "all"
    sort: Literal["created_at", "last_message_at", "priority"] = "created_at"
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def known_filters(self) -> "ListFilters":
        if self.state and set(self.state.split(",")) - {
            "new",
            "open",
            "pending_customer",
            "resolved",
            "closed",
        }:
            raise ValueError("Choose supported states")
        if self.priority and set(self.priority.split(",")) - {"urgent", "high", "normal", "low"}:
            raise ValueError("Choose supported priorities")
        return self


class PortalFilters(Input):
    q: str = Field(default="", max_length=200)
    state: str | None = Field(default=None, max_length=150)
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def known_states(self) -> "PortalFilters":
        ListFilters(state=self.state)
        return self


class MessageFilters(Input):
    after_sequence: int = Field(default=0, ge=0)
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)


class HistoryFilters(Input):
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)
