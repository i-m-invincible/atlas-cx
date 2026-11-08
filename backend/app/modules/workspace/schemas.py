from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StrictBool, field_validator, model_validator

from app.modules.customers.schemas import ContactView
from app.modules.identity.schemas import Role
from app.platform.config import Settings
from app.platform.protocol import Input


class WorkspaceView(BaseModel):
    id: UUID
    version: int
    name: str
    slug: str
    timezone: str
    feedback_manager_member_id: UUID | None
    capabilities: dict[str, bool] = {"customers": True, "cases": False}
    active_case_config_id: UUID | None = None
    active_health_profile_id: None = None


class WorkspacePatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    timezone: str | None = None
    feedback_manager_member_id: UUID | None = None

    @model_validator(mode="after")
    def valid_patch(self) -> "WorkspacePatch":
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Include a nonempty change")
        if self.timezone:
            Settings.valid_timezone(self.timezone)
        return self


class MemberCreate(Input):
    email: EmailStr = Field(max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    role: Role


class MemberPatch(Input):
    role: Role | None = None
    active: StrictBool | None = None
    replacement_member_id: UUID | None = None

    @model_validator(mode="after")
    def valid_patch(self) -> "MemberPatch":
        if not ({"role", "active"} & self.model_fields_set):
            raise ValueError("Include a role or access change")
        if any(
            getattr(self, key) is None for key in self.model_fields_set - {"replacement_member_id"}
        ):
            raise ValueError("Role and active cannot be null")
        return self


class MemberView(BaseModel):
    id: UUID
    version: int
    user_id: UUID
    display_name: str
    email: str
    role: Role
    active: bool
    created_at: datetime


class MemberSetupView(BaseModel):
    member: MemberView
    setup_url: str


class PortalSetupView(BaseModel):
    contact: ContactView
    setup_url: str


class AccessPatch(Input):
    active: StrictBool


class TeamCreate(Input):
    name: str = Field(min_length=1, max_length=120)
    member_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("member_ids")
    @classmethod
    def unique_members(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Choose each member once")
        return value


class TeamPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    member_ids: list[UUID] | None = Field(default=None, max_length=100)
    archived: StrictBool | None = None

    @model_validator(mode="after")
    def valid_patch(self) -> "TeamPatch":
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Include a nonempty change")
        if self.member_ids:
            TeamCreate.unique_members(self.member_ids)
        return self


class TeamView(BaseModel):
    id: UUID
    version: int
    name: str
    member_ids: list[UUID]
    archived_at: datetime | None
    created_at: datetime


class PageFilters(Input):
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)


class MemberFilters(PageFilters):
    active: bool | None = None
    role: Role | None = None


class AuditView(BaseModel):
    sequence: int
    action: str
    entity_type: str
    entity_id: UUID | None
    actor_user_id: UUID | None
    changed_fields: list[str]
    reason: str | None
    request_id: str
    occurred_at: datetime
