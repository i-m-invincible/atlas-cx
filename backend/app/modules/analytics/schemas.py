from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.activities.schemas import PageFilters
from app.platform.protocol import Input

Bucket = Literal["day", "week"]
ReportKind = Literal["cases", "tasks", "feedback"]
Metric = Literal[
    "new_cases",
    "backlog",
    "unassigned",
    "response_overdue",
    "resolution_overdue",
    "paused",
    "first_response",
    "resolution",
    "reopen",
    "csat",
    "coverage",
    "follow_up",
]


class ReportFilters(Input):
    from_: str | None = Field(default=None, alias="from", max_length=40)
    to: str | None = Field(default=None, max_length=40)
    timezone: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,50}$")
    team_id: UUID | None = None


class TrendFilters(ReportFilters):
    bucket: Bucket = "day"


class ExportFilters(ReportFilters):
    report: ReportKind


class RecordFilters(ReportFilters, PageFilters):
    metric: Metric


class ReportScope(BaseModel):
    from_at: datetime
    to_at: datetime
    timezone: str
    category: str | None
    team_id: UUID | None
    generated_at: datetime
    as_of: datetime
    today_partial: bool


class Rate(BaseModel):
    numerator: int
    denominator: int
    share: float | None


class Durations(BaseModel):
    median_seconds: float | None
    p90_seconds: float | None
    sample_count: int
    attainment: Rate


class CategoryVolume(BaseModel):
    key: str
    label: str
    count: int


class Overview(BaseModel):
    scope: ReportScope
    new_cases: int
    active_backlog: int
    unassigned: int
    unanswered_overdue: int
    resolution_overdue: int
    paused: int
    first_response: Durations
    resolution: Durations
    reopen: Rate
    immature_cycles: int
    csat: Rate
    coverage: Rate
    follow_up: Rate
    categories: list[CategoryVolume]
    trend: "Trends"


class TrendPoint(BaseModel):
    start: date
    count: int
    categories: dict[str, int]
    partial: bool


class Trends(BaseModel):
    scope: ReportScope
    bucket: Bucket
    points: list[TrendPoint]


class MetricRecord(BaseModel):
    id: UUID
    record_type: Literal["case", "task", "feedback"]
    reference_id: UUID
    title: str
    observed_at: datetime
    eligible: bool = True
    meets_measure: bool | None = None
    seconds: float | None = None
    cycle_number: int | None = None
