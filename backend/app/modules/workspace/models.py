from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_workspace_version"),
        ForeignKeyConstraint(
            ["id", "active_case_config_id"],
            ["case_config_versions.workspace_id", "case_config_versions.id"],
            name="fk_workspace_case_config",
            use_alter=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    feedback_manager_member_id: Mapped[UUID | None]
    active_case_config_id: Mapped[UUID | None]
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(default=False, server_default="false")
