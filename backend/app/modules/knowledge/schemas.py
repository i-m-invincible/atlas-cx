from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.activities.schemas import PageFilters
from app.modules.knowledge.content import MAX_TEXT, SourceKind, normalize
from app.platform.protocol import Input

RevisionState = Literal["draft", "queued", "indexing", "ready", "failed"]
RequestState = Literal["queued", "running", "completed", "failed"]
Mode = Literal["generated", "sources_only", "abstained"]
JobKind = Literal["knowledge_index", "assistant_request"]
JobState = Literal["queued", "running", "succeeded", "failed"]
Title = Annotated[str, Field(min_length=1, max_length=200)]
CanonicalText = Annotated[
    str, StringConstraints(min_length=1, max_length=MAX_TEXT, strip_whitespace=False)
]


class Draft(Input):
    title: Title | None = None
    content_text: CanonicalText
    source_kind: SourceKind = "pasted"
    source_name: Title | None = None

    @field_validator("content_text", mode="before")
    @classmethod
    def canonical_content(cls, value: object) -> object:
        return normalize(value) if isinstance(value, str) else value


class NewDocument(Draft):
    title: Title


class DraftPatch(Input):
    content_text: CanonicalText | None = None
    title: Title | None = None

    @field_validator("content_text", mode="before")
    @classmethod
    def canonical_content(cls, value: object) -> object:
        return Draft.canonical_content(value)

    @model_validator(mode="after")
    def changes(self) -> "DraftPatch":
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("Include a title or draft text")
        return self


class Archive(Input):
    reason: str = Field(min_length=1, max_length=1000)


class Empty(Input):
    pass


class DocumentFilters(PageFilters):
    q: str | None = Field(default=None, max_length=200)
    status: Literal["published", "draft", "queued", "indexing", "failed", "archived"] | None = None


class RevisionSummary(BaseModel):
    id: UUID
    document_id: UUID
    title: str
    revision_number: int
    version: int
    source_kind: SourceKind
    source_name: str | None
    content_sha256: str
    status: RevisionState
    embedding_model_revision: str | None
    error_code: str | None
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    active_version_id: UUID | None


class RevisionView(RevisionSummary):
    content_text: str


class DocumentView(BaseModel):
    id: UUID
    title: str
    version: int
    active_version_id: UUID | None
    active_revision_number: int | None
    pending_version_id: UUID | None
    latest_revision: RevisionSummary | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentView):
    revisions: list[RevisionSummary]


class Publication(BaseModel):
    revision: RevisionSummary
    job_id: UUID
    poll_url: str


class SearchFilters(Input):
    q: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=20)


class Source(BaseModel):
    document_id: UUID
    version_id: UUID
    chunk_id: UUID
    title: str
    revision_number: int
    ordinal: int
    heading_path: list[str]
    start_offset: int
    end_offset: int
    excerpt: str
    source_url: str


class AssistantSource(Source):
    label: str
    rank: int


class Question(Input):
    question: str = Field(min_length=1, max_length=2000)
    case_id: UUID | None = None


class Answer(BaseModel):
    id: UUID
    state: RequestState
    mode: Mode | None
    answer_text: str | None
    abstention_reason: str | None
    error_code: str | None
    sources: list[AssistantSource]
    model_id: str | None
    case_id: UUID | None
    delayed: bool
    completed_at: datetime | None
    created_at: datetime
    poll_url: str
    feedback: bool | None


class FeedbackInput(Input):
    helpful: StrictBool
    reason: str | None = Field(default=None, max_length=1000)


class JobFilters(PageFilters):
    kind: JobKind | None = None
    status: JobState | None = None


class JobView(BaseModel):
    id: UUID
    kind: JobKind
    status: JobState
    attempts: int
    heartbeat_at: datetime | None
    last_error_code: str | None
    finished_at: datetime | None
    created_at: datetime
    available_at: datetime
    version: int


class Availability(BaseModel):
    source_search: bool
    indexing_worker_seen_at: datetime | None
    generation_configured: bool
