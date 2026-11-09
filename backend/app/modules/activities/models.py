from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class EventDefinition(Base):
    __tablename__ = "event_definitions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "key"),
        CheckConstraint("version > 0 AND jsonb_typeof(allowed_properties_json) = 'object'"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    key: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(120))
    allowed_properties_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    counts_as_activity: Mapped[bool]
    enabled: Mapped[bool]
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomerEvent(Base):
    __tablename__ = "customer_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "external_event_id"),
        ForeignKeyConstraint(
            ["workspace_id", "customer_id"], ["customers.workspace_id", "customers.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "event_definition_id"],
            ["event_definitions.workspace_id", "event_definitions.id"],
        ),
        CheckConstraint("jsonb_typeof(safe_properties) = 'object'"),
        Index("ix_customer_events_timeline", "workspace_id", "customer_id", "occurred_at", "id"),
        Index("ix_customer_events_retention", "workspace_id", "received_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    customer_id: Mapped[UUID]
    event_definition_id: Mapped[UUID]
    external_event_id: Mapped[str] = mapped_column(String(120))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    safe_properties: Mapped[dict[str, object]] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    activity_flag_snapshot: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
