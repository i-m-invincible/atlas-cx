from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, JsonValue

ImportStatus = Literal["validated", "committed", "failed", "expired"]


class CsvRow(BaseModel):
    row: int
    cells: dict[str, str]


class RowIssue(BaseModel):
    field: str
    message: str


class ImportRow(BaseModel):
    row: int
    action: Literal["create", "update", "error"]
    values: dict[str, JsonValue]
    errors: list[RowIssue]
    customer_id: UUID | None = None
    customer_version: int | None = None


class ImportView(BaseModel):
    id: UUID
    version: int
    status: ImportStatus
    create_count: int
    update_count: int
    error_count: int
    rows: list[ImportRow]
    expires_at: datetime
    created_at: datetime
    completed_at: datetime | None
