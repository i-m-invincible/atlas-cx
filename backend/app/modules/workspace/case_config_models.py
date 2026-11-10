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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class CaseConfig(Base):
    __tablename__ = "case_config_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "number"),
        ForeignKeyConstraint(
            ["workspace_id", "created_by_member_id"], ["memberships.workspace_id", "memberships.id"]
        ),
        CheckConstraint("status IN ('draft','published')"),
        CheckConstraint("number > 0 AND version > 0"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    number: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(16))
    definition_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_by_member_id: Mapped[UUID]
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
