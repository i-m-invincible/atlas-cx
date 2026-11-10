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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "external_id"),
        ForeignKeyConstraint(
            ["workspace_id", "owner_member_id"], ["memberships.workspace_id", "memberships.id"]
        ),
        CheckConstraint("kind IN ('person','business')"),
        CheckConstraint("lifecycle IN ('prospect','active','inactive')"),
        CheckConstraint("version > 0"),
        CheckConstraint("cardinality(tags) <= 20"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(16))
    lifecycle: Mapped[str] = mapped_column(String(16), default="active")
    external_id: Mapped[str | None] = mapped_column(String(120))
    owner_member_id: Mapped[UUID | None]
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    activity_expected: Mapped[bool] = mapped_column(default=False)
    tracking_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "customer_id", "id"),
        UniqueConstraint("workspace_id", "normalized_email"),
        ForeignKeyConstraint(
            ["workspace_id", "customer_id"], ["customers.workspace_id", "customers.id"]
        ),
        CheckConstraint("version > 0"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    customer_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(120))
    normalized_email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
