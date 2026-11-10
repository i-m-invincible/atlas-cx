from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.database import Base


class TenantRow:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Versioned(TenantRow):
    version: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Document(Versioned, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "created_by_member_id"], ["memberships.workspace_id", "memberships.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "id", "active_version_id"],
            [
                "knowledge_versions.workspace_id",
                "knowledge_versions.document_id",
                "knowledge_versions.id",
            ],
            name="fk_knowledge_active",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["workspace_id", "id", "pending_version_id"],
            [
                "knowledge_versions.workspace_id",
                "knowledge_versions.document_id",
                "knowledge_versions.id",
            ],
            name="fk_knowledge_pending",
            use_alter=True,
        ),
        CheckConstraint("version > 0 AND length(btrim(title)) BETWEEN 1 AND 200"),
        CheckConstraint(
            "archived_at IS NULL OR (active_version_id IS NULL AND pending_version_id IS NULL)"
        ),
        Index("ix_knowledge_documents_recent", "workspace_id", "created_at", "id"),
    )
    title: Mapped[str] = mapped_column(String(200))
    active_version_id: Mapped[UUID | None]
    pending_version_id: Mapped[UUID | None]
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_member_id: Mapped[UUID]


class Revision(Versioned, Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "document_id", "id"),
        UniqueConstraint("workspace_id", "document_id", "revision_number"),
        ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "published_by_member_id"],
            ["memberships.workspace_id", "memberships.id"],
        ),
        CheckConstraint("version > 0 AND revision_number > 0"),
        CheckConstraint("source_kind IN ('pasted','txt','markdown')"),
        CheckConstraint("status IN ('draft','queued','indexing','ready','failed')"),
        CheckConstraint("length(content_text) BETWEEN 1 AND 200000"),
        CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 200 AND content_sha256 ~ '^[0-9a-f]{64}$'"
        ),
        CheckConstraint(
            "(status = 'ready') = (indexed_at IS NOT NULL AND embedding_model_revision IS NOT NULL)"
        ),
    )
    document_id: Mapped[UUID]
    revision_number: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    source_kind: Mapped[str] = mapped_column(String(10))
    source_name: Mapped[str | None] = mapped_column(String(200))
    content_text: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="draft")
    embedding_model_revision: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(50))
    published_by_member_id: Mapped[UUID | None]
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Chunk(TenantRow, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "version_id", "id"),
        UniqueConstraint("workspace_id", "version_id", "ordinal"),
        ForeignKeyConstraint(
            ["workspace_id", "version_id"],
            ["knowledge_versions.workspace_id", "knowledge_versions.id"],
        ),
        CheckConstraint("ordinal >= 0 AND start_offset >= 0 AND end_offset > start_offset"),
        CheckConstraint(
            "char_length(content) = end_offset - start_offset AND token_count BETWEEN 1 AND 180"
        ),
        CheckConstraint("jsonb_typeof(heading_path) = 'array'"),
        Index("ix_knowledge_chunk_search", "search_tsvector", postgresql_using="gin"),
    )
    version_id: Mapped[UUID]
    ordinal: Mapped[int]
    heading_path: Mapped[list[str]] = mapped_column(JSONB)
    start_offset: Mapped[int]
    end_offset: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    embedding_model_revision: Mapped[str] = mapped_column(String(100))
    search_tsvector: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english'::regconfig, content)", persisted=True)
    )


class AssistantRequest(TenantRow, Base):
    __tablename__ = "assistant_requests"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "id", "requested_by_member_id"),
        ForeignKeyConstraint(
            ["workspace_id", "requested_by_member_id"],
            ["memberships.workspace_id", "memberships.id"],
        ),
        ForeignKeyConstraint(["workspace_id", "case_id"], ["cases.workspace_id", "cases.id"]),
        CheckConstraint("state IN ('queued','running','completed','failed')"),
        CheckConstraint("mode IS NULL OR mode IN ('generated','sources_only','abstained')"),
        CheckConstraint("question IS NULL OR length(question) BETWEEN 1 AND 2000"),
        CheckConstraint("source_count BETWEEN 0 AND 6"),
        Index(
            "ix_assistant_member_requests",
            "workspace_id",
            "requested_by_member_id",
            "state",
            "created_at",
        ),
    )
    requested_by_member_id: Mapped[UUID]
    # Session IDs are retained as provenance without blocking session expiry cleanup.
    requested_by_session_id: Mapped[UUID]
    question: Mapped[str | None] = mapped_column(Text)
    case_id: Mapped[UUID | None]
    state: Mapped[str] = mapped_column(String(12), default="queued")
    answer_text: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(String(16))
    source_count: Mapped[int] = mapped_column(default=0)
    abstention_reason: Mapped[str | None] = mapped_column(String(50))
    model_id: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    retrieval_version: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(50))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Citation(TenantRow, Base):
    __tablename__ = "assistant_citations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "request_id", "label"),
        UniqueConstraint("workspace_id", "request_id", "rank"),
        ForeignKeyConstraint(
            ["workspace_id", "request_id"],
            ["assistant_requests.workspace_id", "assistant_requests.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "document_id", "version_id"],
            [
                "knowledge_versions.workspace_id",
                "knowledge_versions.document_id",
                "knowledge_versions.id",
            ],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "version_id", "chunk_id"],
            ["knowledge_chunks.workspace_id", "knowledge_chunks.version_id", "knowledge_chunks.id"],
        ),
        CheckConstraint("rank BETWEEN 1 AND 6 AND label = 'S' || CAST(rank AS text)"),
        CheckConstraint("start_offset >= 0 AND end_offset > start_offset"),
    )
    request_id: Mapped[UUID]
    label: Mapped[str] = mapped_column(String(5))
    document_id: Mapped[UUID]
    version_id: Mapped[UUID]
    chunk_id: Mapped[UUID]
    excerpt: Mapped[str | None] = mapped_column(Text)
    start_offset: Mapped[int]
    end_offset: Mapped[int]
    rank: Mapped[int]


class AssistantFeedback(TenantRow, Base):
    __tablename__ = "assistant_feedback"
    __table_args__ = (
        UniqueConstraint("workspace_id", "request_id", "member_id"),
        ForeignKeyConstraint(
            ["workspace_id", "request_id", "member_id"],
            [
                "assistant_requests.workspace_id",
                "assistant_requests.id",
                "assistant_requests.requested_by_member_id",
            ],
        ),
        CheckConstraint("reason IS NULL OR length(reason) <= 1000"),
    )
    request_id: Mapped[UUID]
    member_id: Mapped[UUID]
    helpful: Mapped[bool]
    reason: Mapped[str | None] = mapped_column(String(1000))
