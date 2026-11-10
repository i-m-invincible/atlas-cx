from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    normalized_email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(String(512))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint("role IN ('admin','manager','agent','viewer')"),
        CheckConstraint("NOT active OR setup_completed_at IS NOT NULL"),
        CheckConstraint("version > 0"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(16))
    invited_display_name: Mapped[str | None] = mapped_column(String(120))
    setup_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PortalBinding(Base):
    __tablename__ = "portal_bindings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "user_id"),
        UniqueConstraint("workspace_id", "contact_id"),
        ForeignKeyConstraint(
            ["workspace_id", "contact_id"], ["contacts.workspace_id", "contacts.id"]
        ),
        CheckConstraint("version > 0"),
        CheckConstraint("NOT active OR setup_completed_at IS NOT NULL"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    contact_id: Mapped[UUID]
    setup_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("audience IN ('staff','portal')"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_secret_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    audience: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SetupToken(Base):
    __tablename__ = "setup_tokens"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "membership_id"], ["memberships.workspace_id", "memberships.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "portal_binding_id"],
            ["portal_bindings.workspace_id", "portal_bindings.id"],
        ),
        CheckConstraint(
            "(purpose = 'staff_setup' AND workspace_id IS NOT NULL "
            "AND membership_id IS NOT NULL AND portal_binding_id IS NULL) OR "
            "(purpose = 'portal_setup' AND workspace_id IS NOT NULL "
            "AND membership_id IS NULL AND portal_binding_id IS NOT NULL) OR "
            "(purpose = 'recovery' AND workspace_id IS NULL "
            "AND membership_id IS NULL AND portal_binding_id IS NULL)"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    workspace_id: Mapped[UUID | None] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    membership_id: Mapped[UUID | None]
    portal_binding_id: Mapped[UUID | None]
    purpose: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    principal_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    failures: Mapped[int] = mapped_column(default=0)
