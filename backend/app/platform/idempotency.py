"""Metadata-only replay protection, always after current authorization."""

import hashlib
import json
import re
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.auth import UnitOfWork
from app.platform.database import Base
from app.platform.protocol import Fault, now


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("workspace_id", "principal_key", "route_key", "key"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    principal_key: Mapped[str] = mapped_column(String(100))
    route_key: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(20))
    resource_id: Mapped[UUID | None]
    response_status: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def prepare(
    uow: UnitOfWork, request: Request, payload: BaseModel
) -> tuple[IdempotencyRecord, bool]:
    key = request.headers.get("Idempotency-Key", "")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
        raise Fault(
            400, "idempotency_key_required", "Provide a unique Idempotency-Key for this action."
        )
    principal = f"{uow.scope.audience}:{uow.scope.user_id}"
    # Include the concrete target ID: a key cannot replay against another case.
    route = request.url.path
    payload_hash = hashlib.sha256(
        json.dumps(
            payload.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    row = uow.session.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.principal_key == principal,
            IdempotencyRecord.route_key == route,
            IdempotencyRecord.key == key,
        )
        .with_for_update()
    )
    if row and row.expires_at > now():
        if row.request_hash != payload_hash:
            raise Fault(
                409, "idempotency_conflict", "This key was already used for a different action."
            )
        return row, True
    if not row:
        row = IdempotencyRecord(
            workspace_id=uow.scope.workspace_id, principal_key=principal, route_key=route, key=key
        )
        uow.session.add(row)
    row.request_hash = payload_hash
    row.resource_id, row.resource_type, row.response_status = None, None, 0
    row.expires_at = now() + timedelta(hours=24)
    return row, False


def complete(
    row: IdempotencyRecord, resource_type: str, identifier: UUID, status: int = 200
) -> None:
    row.resource_type, row.resource_id, row.response_status = resource_type, identifier, status
