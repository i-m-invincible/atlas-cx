from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.platform.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (UniqueConstraint("workspace_id", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_kind: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[UUID | None]
    changed_fields: Mapped[list[str]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(String(2000))
    request_id: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def record_audit(
    session: Session,
    workspace_id: UUID,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    fields: list[str],
    request_id: str,
    reason: str | None = None,
) -> None:
    session.add(
        AuditEvent(
            workspace_id=workspace_id,
            actor_user_id=actor_id,
            actor_kind="staff" if actor_id else "operator",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changed_fields=sorted(fields),
            request_id=request_id,
            reason=reason,
        )
    )
