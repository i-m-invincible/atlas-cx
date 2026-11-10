from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from app.platform.protocol import Input

EventKey = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,50}$")]
Scalar = StrictStr | StrictBool | StrictInt | StrictFloat
TimelineKind = Literal["message", "transition", "event", "task", "feedback"]


class PropertyRule(Input):
    type: Literal["string", "integer", "number", "boolean"]
    max_length: int | None = Field(default=None, ge=1, le=8192, strict=True)

    @model_validator(mode="after")
    def length_rule(self) -> "PropertyRule":
        if (self.max_length is not None) != (self.type == "string"):
            raise ValueError("Only string properties require a length limit")
        return self


class DefinitionCreate(Input):
    key: EventKey
    label: str = Field(min_length=1, max_length=120)
    allowed_properties: dict[EventKey, PropertyRule] = Field(default_factory=dict, max_length=20)
    counts_as_activity: StrictBool
    enabled: StrictBool = True


class DefinitionPatch(Input):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    allowed_properties: dict[EventKey, PropertyRule] | None = Field(default=None, max_length=20)
    counts_as_activity: StrictBool | None = None
    enabled: StrictBool | None = None

    @model_validator(mode="after")
    def changes(self) -> "DefinitionPatch":
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Include at least one non-null change")
        return self


class DefinitionView(DefinitionCreate):
    id: UUID
    version: int
    created_at: datetime
    updated_at: datetime


class EventInput(Input):
    model_config = ConfigDict(str_strip_whitespace=False)

    external_event_id: str = Field(min_length=1, max_length=120)
    customer_external_id: str = Field(min_length=1, max_length=120)
    event_name: EventKey
    occurred_at: AwareDatetime
    properties: dict[EventKey, Scalar] = Field(default_factory=dict, max_length=20)

    @field_validator("external_event_id", "customer_external_id")
    @classmethod
    def valid_identifier(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("Use a non-blank identifier without null characters")
        value.encode("utf-8")
        return value

    @field_validator("occurred_at", mode="before")
    @classmethod
    def timestamp_text(cls, value: object) -> object:
        if not isinstance(value, (str, datetime)):
            raise ValueError("Use a timezone-aware timestamp")
        return value


class EventBatch(Input):
    events: list[EventInput] = Field(min_length=1, max_length=100)


class IngestResult(BaseModel):
    received_count: int
    inserted_count: int
    duplicate_count: int
    ids: list[UUID]


class EventView(BaseModel):
    id: UUID
    external_event_id: str
    event_name: str
    event_label: str
    occurred_at: datetime
    received_at: datetime
    properties: dict[str, Scalar]
    counts_as_activity: bool


class PageFilters(Input):
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)


class EventFilters(PageFilters):
    event_name: EventKey | None = None
    from_: AwareDatetime | None = Field(default=None, alias="from")
    to: AwareDatetime | None = None

    @model_validator(mode="after")
    def interval(self) -> "EventFilters":
        if self.from_ and self.to and self.from_ >= self.to:
            raise ValueError("Choose a start before the end")
        return self


class TimelineFilters(PageFilters):
    kinds: str | None = Field(default=None, max_length=100)

    @field_validator("kinds")
    @classmethod
    def known_kinds(cls, value: str | None) -> str | None:
        if value and set(value.split(",")) - {"message", "transition", "event", "task", "feedback"}:
            raise ValueError("Choose supported timeline kinds")
        return value


class TimelineEntry(BaseModel):
    id: UUID
    kind: TimelineKind
    occurred_at: datetime
    received_at: datetime | None
    title: str
    reference_id: UUID
    preview: str
    actor: str
