from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StrictBool, field_validator, model_validator

from app.platform.protocol import Input

Lifecycle = Literal["prospect", "active", "inactive"]


class CustomerCreate(Input):
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["person", "business"]
    lifecycle: Lifecycle = "active"
    external_id: str | None = Field(default=None, min_length=1, max_length=120)
    owner_member_id: UUID | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    activity_expected: StrictBool = False
    tracking_started_at: datetime | None = None

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, value: list[str]) -> list[str]:
        value = [tag.strip() for tag in value]
        if len(set(value)) != len(value) or any(not tag or len(tag) > 40 for tag in value):
            raise ValueError("Use up to 20 unique tags, each 1–40 characters")
        return value

    @field_validator("tracking_started_at")
    @classmethod
    def aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Include a timezone")
        return value


class CustomerPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    lifecycle: Lifecycle | None = None
    external_id: str | None = Field(default=None, min_length=1, max_length=120)
    owner_member_id: UUID | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    activity_expected: StrictBool | None = None
    tracking_started_at: datetime | None = None

    @model_validator(mode="after")
    def valid_patch(self) -> "CustomerPatch":
        if not self.model_fields_set:
            raise ValueError("Include at least one change")
        for field in {
            "name",
            "lifecycle",
            "tags",
            "activity_expected",
            "external_id",
        } & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if self.tags is not None:
            self.tags = CustomerCreate.valid_tags(self.tags)
        CustomerCreate.aware_timestamp(self.tracking_started_at)
        return self


class CustomerView(BaseModel):
    id: UUID
    version: int
    name: str
    kind: str
    lifecycle: str
    external_id: str | None
    owner_member_id: UUID | None
    owner_name: str | None
    tags: list[str]
    activity_expected: bool
    tracking_started_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    latest_health: None = None
    last_meaningful_activity_at: None = None


class ContactCreate(Input):
    customer_id: UUID
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=254)
    phone: str | None = Field(default=None, max_length=32)


class ContactPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def valid_patch(self) -> "ContactPatch":
        if not self.model_fields_set:
            raise ValueError("Include at least one change")
        if ("name" in self.model_fields_set and self.name is None) or (
            "email" in self.model_fields_set and self.email is None
        ):
            raise ValueError("Name and email cannot be null")
        return self


class ContactView(BaseModel):
    id: UUID
    customer_id: UUID
    version: int
    name: str
    email: str
    phone: str | None
    archived_at: datetime | None
    portal_enabled: bool
    created_at: datetime
    updated_at: datetime


class CustomerFilters(Input):
    q: str = Field(default="", max_length=200)
    lifecycle: str | None = None
    owner_id: UUID | None = None
    tag: str | None = Field(default=None, max_length=40)
    archived: bool = False
    sort: Literal["created_at", "name"] = "created_at"
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)

    @field_validator("lifecycle")
    @classmethod
    def known_lifecycles(cls, value: str | None) -> str | None:
        if value and any(
            part not in {"prospect", "active", "inactive"} for part in value.split(",")
        ):
            raise ValueError("Choose a supported lifecycle")
        return value


class ContactFilters(Input):
    customer_id: UUID | None = None
    q: str = Field(default="", max_length=200)
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)


class ArchiveInput(Input):
    reason: str = Field(min_length=1, max_length=2000)
