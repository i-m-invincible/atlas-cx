from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class WorkspaceCounter(Base):
    __tablename__ = "workspace_counters"
    __table_args__ = (CheckConstraint("next_case_number > 0"),)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    next_case_number: Mapped[int] = mapped_column(BigInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "number"),
        UniqueConstraint("workspace_id", "customer_id", "id", name="uq_case_customer_reference"),
        UniqueConstraint(
            "workspace_id", "id", "requester_contact_id", name="uq_case_requester_reference"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "customer_id", "requester_contact_id"],
            ["contacts.workspace_id", "contacts.customer_id", "contacts.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "customer_id"], ["customers.workspace_id", "customers.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "config_version_id"],
            ["case_config_versions.workspace_id", "case_config_versions.id"],
        ),
        ForeignKeyConstraint(["workspace_id", "team_id"], ["teams.workspace_id", "teams.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "assignee_member_id"], ["memberships.workspace_id", "memberships.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "related_case_id"], ["cases.workspace_id", "cases.id"]
        ),
        CheckConstraint("state IN ('new','open','pending_customer','resolved','closed')"),
        CheckConstraint("priority IN ('urgent','high','normal','low')"),
        CheckConstraint("source IN ('portal','manual_phone','manual_email','manual_other')"),
        CheckConstraint("version > 0 AND number > 0 AND current_cycle_number > 0"),
        CheckConstraint("first_response_target_seconds > 0 AND resolution_target_seconds > 0"),
        CheckConstraint("state = 'new' OR assignee_member_id IS NOT NULL"),
        CheckConstraint("related_case_id IS NULL OR related_case_id != id"),
        Index("ix_cases_queue", "workspace_id", "state", "priority", "created_at", "id"),
        Index("ix_cases_assignee", "workspace_id", "assignee_member_id", "state"),
        Index("ix_cases_customer", "workspace_id", "customer_id", "created_at", "id"),
        Index("ix_cases_last_message", "workspace_id", "last_message_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    number: Mapped[int] = mapped_column(BigInteger)
    customer_id: Mapped[UUID]
    requester_contact_id: Mapped[UUID]
    config_version_id: Mapped[UUID]
    category_key: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), default="new")
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    team_id: Mapped[UUID | None]
    assignee_member_id: Mapped[UUID | None]
    custom_values: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    related_case_id: Mapped[UUID | None]
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_target_seconds: Mapped[int]
    resolution_target_seconds: Mapped[int]
    last_public_message_seq: Mapped[int | None] = mapped_column(BigInteger)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_cycle_number: Mapped[int] = mapped_column(default=1)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CaseCycle(Base):
    __tablename__ = "case_cycles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "case_id", "cycle_number"),
        ForeignKeyConstraint(["workspace_id", "case_id"], ["cases.workspace_id", "cases.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "resolved_by_member_id"],
            ["memberships.workspace_id", "memberships.id"],
        ),
        CheckConstraint("cycle_number > 0 AND target_seconds > 0 AND paused_seconds >= 0"),
        CheckConstraint("resolved_at IS NULL OR resolved_at >= opened_at"),
        CheckConstraint("pause_started_at IS NULL OR pause_started_at >= opened_at"),
        CheckConstraint(
            "resolved_at IS NULL OR (pause_started_at IS NULL "
            "AND resolved_by_member_id IS NOT NULL AND resolution_code IS NOT NULL "
            "AND length(btrim(resolution_summary)) > 0)"
        ),
        CheckConstraint(
            "resolution_code IS NULL OR resolution_code IN "
            "('answered','fixed','fulfilled','declined','duplicate','other')"
        ),
        Index(
            "uq_case_unfinished_cycle",
            "workspace_id",
            "case_id",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
        Index("ix_case_cycle_resolution", "workspace_id", "resolved_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    case_id: Mapped[UUID]
    cycle_number: Mapped[int]
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_seconds: Mapped[int]
    paused_seconds: Mapped[float] = mapped_column(default=0.0)
    pause_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_member_id: Mapped[UUID | None]
    resolution_code: Mapped[str | None] = mapped_column(String(20))
    resolution_summary: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("case_id", "sequence"),
        UniqueConstraint("workspace_id", "case_id", "id"),
        ForeignKeyConstraint(["workspace_id", "case_id"], ["cases.workspace_id", "cases.id"]),
        CheckConstraint("author_kind IN ('staff','contact','system')"),
        CheckConstraint("visibility IN ('public','internal')"),
        CheckConstraint(
            "message_kind IN ('initial','reply','note','resolution','info_request','reopen')"
        ),
        CheckConstraint("length(btrim(body)) BETWEEN 1 AND 10000"),
        CheckConstraint(
            "(visibility = 'internal' AND message_kind = 'note' AND author_kind = 'staff') "
            "OR (visibility = 'public' AND message_kind != 'note')"
        ),
        CheckConstraint("updated_case_version > 0"),
        Index("ix_messages_conversation", "workspace_id", "case_id", "sequence"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    case_id: Mapped[UUID]
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    author_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    author_kind: Mapped[str] = mapped_column(String(10))
    visibility: Mapped[str] = mapped_column(String(10))
    message_kind: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    updated_case_version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReadMarker(Base):
    __tablename__ = "case_read_markers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "case_id", "member_id"),
        ForeignKeyConstraint(["workspace_id", "case_id"], ["cases.workspace_id", "cases.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "member_id"], ["memberships.workspace_id", "memberships.id"]
        ),
        CheckConstraint("last_read_sequence >= 0"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    case_id: Mapped[UUID]
    member_id: Mapped[UUID]
    last_read_sequence: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseTransition(Base):
    __tablename__ = "case_transitions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "case_id", "cycle_number"],
            ["case_cycles.workspace_id", "case_cycles.case_id", "case_cycles.cycle_number"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "case_id", "message_id"],
            ["messages.workspace_id", "messages.case_id", "messages.id"],
        ),
        CheckConstraint("to_state IN ('new','open','pending_customer','resolved','closed')"),
        CheckConstraint(
            "from_state IS NULL OR from_state IN "
            "('new','open','pending_customer','resolved','closed')"
        ),
        Index("ix_case_transition_time", "workspace_id", "case_id", "occurred_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    case_id: Mapped[UUID]
    cycle_number: Mapped[int]
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(4000))
    message_id: Mapped[UUID | None]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
