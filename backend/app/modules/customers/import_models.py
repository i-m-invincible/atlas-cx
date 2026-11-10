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


class CustomerImport(Base):
    __tablename__ = "customer_imports"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "submitted_by_member_id"],
            ["memberships.workspace_id", "memberships.id"],
        ),
        CheckConstraint("status IN ('validated','committed','failed','expired')"),
        CheckConstraint(
            "version > 0 AND create_count >= 0 AND update_count >= 0 AND error_count >= 0"
        ),
        CheckConstraint("jsonb_array_length(normalized_rows_json) <= 1000"),
        Index("ix_customer_imports_expiry", "workspace_id", "expires_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    submitted_by_member_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(String(16), default="validated")
    input_hash: Mapped[str] = mapped_column(String(64))
    normalized_rows_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    row_results_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    create_count: Mapped[int]
    update_count: Mapped[int]
    error_count: Mapped[int]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
