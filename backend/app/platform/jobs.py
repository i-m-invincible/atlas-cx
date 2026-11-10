"""Durable work records shared by the API, dispatcher, and scoped worker."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "dedupe_key"),
        CheckConstraint("kind IN ('knowledge_index','assistant_request')"),
        CheckConstraint("status IN ('queued','running','succeeded','failed')"),
        CheckConstraint("attempts BETWEEN 0 AND 4 AND version > 0"),
        CheckConstraint(
            "(status = 'running') = "
            "(attempt_token IS NOT NULL AND lease_until IS NOT NULL AND locked_by IS NOT NULL)"
        ),
        Index("ix_jobs_claim", "status", "available_at", "lease_until"),
        Index("ix_jobs_workspace_recent", "workspace_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    kind: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[dict[str, str]] = mapped_column(JSONB)
    result_refs_json: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(10), default="queued")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    attempts: Mapped[int] = mapped_column(default=0)
    locked_by: Mapped[str | None] = mapped_column(String(100))
    attempt_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(50))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
