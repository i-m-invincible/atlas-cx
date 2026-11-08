from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.platform.protocol import Input

Role = Literal["admin", "manager", "agent", "viewer"]


class LoginInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    workspace_slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    audience: Literal["staff", "portal"]
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class SetupInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    setup_token: SecretStr = Field(min_length=32, max_length=128)
    new_password: SecretStr | None = Field(default=None, min_length=12, max_length=128)
    current_password: SecretStr | None = Field(default=None, min_length=1, max_length=128)


class IdentityView(BaseModel):
    user_id: UUID
    display_name: str
    email: str
    workspace_id: UUID
    workspace_name: str
    workspace_slug: str
    timezone: str
    audience: Literal["staff", "portal"]
    role: Role | None
    member_id: UUID | None
    contact_id: UUID | None
    permissions: list[str]
    capabilities: dict[str, bool]


class CsrfView(BaseModel):
    csrf_token: str


class MessageView(BaseModel):
    message: str
