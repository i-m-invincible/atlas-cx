from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from app.modules.cases.schemas import Reference
from app.platform.protocol import Input

TaskState = Literal["open", "in_progress", "completed", "cancelled"]


class TaskCreate(Input):
    customer_id: UUID
    case_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    assignee_member_id: UUID
    due_at: AwareDatetime


class TaskPatch(Input):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    assignee_member_id: UUID | None = None
    due_at: AwareDatetime | None = None
    state: TaskState | None = None
    completion_note: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def valid_changes(self) -> "TaskPatch":
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set - {"description"}
        ):
            raise ValueError("Provide a valid change")
        if self.state == "completed" and not self.completion_note:
            raise ValueError("Describe what was done before completing this follow-up")
        if self.completion_note is not None and self.state != "completed":
            raise ValueError("A completion note belongs to a completion")
        return self


class TaskView(BaseModel):
    id: UUID
    version: int
    title: str
    description: str | None
    customer: Reference
    case: Reference | None
    feedback_id: UUID | None
    assignee: Reference
    due_at: datetime
    state: TaskState
    overdue: bool
    completed_at: datetime | None
    completed_by_member_id: UUID | None
    completion_note: str | None
    created_at: datetime
    updated_at: datetime


class TaskHistory(BaseModel):
    id: UUID
    action: str
    occurred_at: datetime
    actor_name: str | None
    changed_fields: list[str]


class PageFilters(Input):
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)


class TaskFilters(PageFilters):
    customer_id: UUID | None = None
    case_id: UUID | None = None
    assignee_id: UUID | None = None
    state: str | None = None
    overdue: bool | None = None
    sort: Literal["due_at", "created_at"] = "due_at"

    @field_validator("state")
    @classmethod
    def states(cls, value: str | None) -> str | None:
        if value and any(
            part not in {"open", "in_progress", "completed", "cancelled"}
            for part in value.split(",")
        ):
            raise ValueError("Choose valid task states")
        return value


class ResolutionFeedback(Input):
    rating: int = Field(ge=1, le=5, strict=True)
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackView(BaseModel):
    id: UUID
    cycle_number: int
    rating: int
    comment: str | None
    created_at: datetime


class StaffFeedbackView(FeedbackView):
    customer: Reference
    case: Reference
    task_id: UUID | None


class FeedbackFilters(PageFilters):
    customer_id: UUID | None = None
    case_id: UUID | None = None
    rating: str | None = None
    from_: AwareDatetime | None = Field(default=None, alias="from")
    to: AwareDatetime | None = None

    @field_validator("rating")
    @classmethod
    def ratings(cls, value: str | None) -> str | None:
        if value and any(part not in {"1", "2", "3", "4", "5"} for part in value.split(",")):
            raise ValueError("Choose ratings from 1 to 5")
        return value
