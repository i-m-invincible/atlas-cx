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
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "case_id", "id"),
        UniqueConstraint("workspace_id", "case_id", "cycle_number"),
        ForeignKeyConstraint(
            ["workspace_id", "case_id", "cycle_number"],
            ["case_cycles.workspace_id", "case_cycles.case_id", "case_cycles.cycle_number"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "case_id", "requester_contact_id"],
            ["cases.workspace_id", "cases.id", "cases.requester_contact_id"],
        ),
        CheckConstraint("rating BETWEEN 1 AND 5"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    case_id: Mapped[UUID]
    cycle_number: Mapped[int]
    requester_contact_id: Mapped[UUID]
    rating: Mapped[int]
    comment: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "feedback_id"),
        ForeignKeyConstraint(
            ["workspace_id", "customer_id"], ["customers.workspace_id", "customers.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "customer_id", "case_id"],
            ["cases.workspace_id", "cases.customer_id", "cases.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "case_id", "feedback_id"],
            ["feedback.workspace_id", "feedback.case_id", "feedback.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "assignee_member_id"], ["memberships.workspace_id", "memberships.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "created_by_member_id"], ["memberships.workspace_id", "memberships.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "completed_by_member_id"],
            ["memberships.workspace_id", "memberships.id"],
        ),
        CheckConstraint("feedback_id IS NULL OR case_id IS NOT NULL"),
        CheckConstraint("state IN ('open','in_progress','completed','cancelled')"),
        CheckConstraint("version > 0 AND length(btrim(title)) > 0"),
        CheckConstraint(
            "(state = 'completed' AND completed_at IS NOT NULL "
            "AND completed_by_member_id IS NOT NULL "
            "AND completion_note IS NOT NULL AND length(btrim(completion_note)) > 0) OR "
            "(state <> 'completed' AND completed_at IS NULL "
            "AND completed_by_member_id IS NULL AND completion_note IS NULL)"
        ),
        Index("ix_tasks_assignment", "workspace_id", "assignee_member_id", "state", "due_at"),
        Index("ix_tasks_customer", "workspace_id", "customer_id", "due_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    customer_id: Mapped[UUID]
    case_id: Mapped[UUID | None]
    feedback_id: Mapped[UUID | None]
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(4000))
    assignee_member_id: Mapped[UUID]
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), default="open")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_member_id: Mapped[UUID | None]
    completion_note: Mapped[str | None] = mapped_column(String(2000))
    created_by_member_id: Mapped[UUID | None]
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
