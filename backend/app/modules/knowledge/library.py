from datetime import datetime
from uuid import UUID

from fastapi import Request
from sqlalchemy import Select, func, select, tuple_

from app.modules.knowledge.content import checksum
from app.modules.knowledge.models import Document, Revision
from app.modules.knowledge.schemas import (
    Archive,
    DocumentDetail,
    DocumentFilters,
    DocumentView,
    Draft,
    DraftPatch,
    Empty,
    NewDocument,
    Publication,
    RevisionSummary,
    RevisionView,
)
from app.platform import idempotency
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role
from app.platform.jobs import Job
from app.platform.protocol import Fault, match_version, missing, now, read_cursor, sign_cursor


def manager(uow: UnitOfWork) -> bool:
    return uow.scope.role in {"admin", "manager"}


def member(uow: UnitOfWork) -> UUID:
    assert uow.scope.member_id
    return uow.scope.member_id


def document(uow: UnitOfWork, identifier: UUID, *, lock: bool = False) -> Document:
    row = uow.session.get(Document, identifier, with_for_update=lock)
    if not row:
        raise missing()
    return row


def revision(uow: UnitOfWork, identifier: UUID, *, lock: bool = False) -> Revision:
    row = uow.session.get(Revision, identifier, with_for_update=lock)
    if not row:
        raise missing()
    return row


def revision_view(row: Revision, doc: Document, *, full: bool = False) -> RevisionSummary:
    schema = RevisionView if full else RevisionSummary
    return schema.model_validate(
        {
            **{key: getattr(row, key) for key in schema.model_fields if key != "active_version_id"},
            "active_version_id": doc.active_version_id,
        }
    )


def revision_detail(uow: UnitOfWork, identifier: UUID) -> RevisionView:
    row = revision(uow, identifier)
    view = revision_view(row, document(uow, row.document_id), full=True)
    assert isinstance(view, RevisionView)
    return view


def summaries(uow: UnitOfWork, documents: list[Document]) -> list[DocumentView]:
    if not documents:
        return []
    ids = [row.id for row in documents]
    latest = {
        row.document_id: row
        for row in uow.session.scalars(
            select(Revision)
            .where(Revision.document_id.in_(ids))
            .distinct(Revision.document_id)
            .order_by(Revision.document_id, Revision.revision_number.desc())
        )
    }
    reference_ids = {
        identifier
        for doc in documents
        for identifier in (doc.active_version_id, doc.pending_version_id)
        if identifier is not None
    }
    by_id = {
        row.id: row
        for row in uow.session.scalars(select(Revision).where(Revision.id.in_(reference_ids)))
    }
    result = []
    for row in documents:
        active = by_id.get(row.active_version_id) if row.active_version_id else None
        pending = by_id.get(row.pending_version_id) if row.pending_version_id else None
        recent = pending or latest.get(row.id)
        result.append(
            DocumentView(
                id=row.id,
                title=row.title,
                version=row.version,
                active_version_id=row.active_version_id,
                active_revision_number=active.revision_number if active else None,
                pending_version_id=row.pending_version_id if manager(uow) else None,
                latest_revision=revision_view(recent, row) if recent else None,
                archived_at=row.archived_at,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    return result


def page_documents(
    uow: UnitOfWork,
    filters: DocumentFilters,
) -> tuple[list[DocumentView], str | None]:
    query: Select[tuple[Document]] = select(Document)
    if filters.status != "archived":
        query = query.where(Document.archived_at.is_(None))
    if filters.status == "archived":
        query = query.where(Document.archived_at.is_not(None))
    elif filters.status == "published":
        query = query.where(Document.active_version_id.is_not(None))
    elif filters.status:
        query = query.where(
            select(Revision.id)
            .where(
                Revision.document_id == Document.id,
                Revision.status == filters.status,
                (Revision.id == Document.pending_version_id) | (Revision.status == "draft"),
            )
            .exists()
        )
    if filters.q:
        pattern = filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Document.title.ilike("%" + pattern + "%"))
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "resource": "knowledge-documents",
        "manager": manager(uow),
        "q": filters.q,
        "status": filters.status,
    }
    if filters.cursor:
        try:
            stamp, identifier = read_cursor(filters.cursor, binding)
            query = query.where(
                tuple_(Document.created_at, Document.id)
                < (datetime.fromisoformat(stamp), UUID(identifier))
            )
        except ValueError:
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    rows = list(
        uow.session.scalars(
            query.order_by(Document.created_at.desc(), Document.id.desc()).limit(filters.limit + 1)
        )
    )
    more = len(rows) > filters.limit
    rows = rows[: filters.limit]
    cursor = (
        sign_cursor(binding, [rows[-1].created_at.isoformat(), str(rows[-1].id)]) if more else None
    )
    return summaries(uow, rows), cursor


def detail(
    uow: UnitOfWork, identifier: UUID, cursor: str | None, limit: int
) -> tuple[DocumentDetail, str | None]:
    doc = document(uow, identifier)
    query = select(Revision).where(Revision.document_id == identifier)
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "resource": "knowledge-revisions",
        "manager": manager(uow),
        "document": str(identifier),
    }
    if cursor:
        try:
            (number,) = read_cursor(cursor, binding)
            query = query.where(Revision.revision_number < int(number))
        except ValueError:
            raise Fault(400, "invalid_cursor", "Return to the first revision page.") from None
    rows = list(
        uow.session.scalars(query.order_by(Revision.revision_number.desc()).limit(limit + 1))
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return DocumentDetail(
        **summaries(uow, [doc])[0].model_dump(),
        revisions=[revision_view(row, doc) for row in rows],
    ), sign_cursor(binding, [str(rows[-1].revision_number)]) if more else None


def audit(
    uow: UnitOfWork, request: Request, action: str, row: Document | Revision, fields: list[str]
) -> None:
    record_audit(
        uow.session,
        row.workspace_id,
        uow.scope.user_id,
        action,
        "knowledge_document" if isinstance(row, Document) else "knowledge_version",
        row.id,
        fields,
        request.state.request_id,
    )


def insert_draft(uow: UnitOfWork, doc: Document, payload: Draft, number: int) -> Revision:
    row = Revision(
        workspace_id=doc.workspace_id,
        document_id=doc.id,
        revision_number=number,
        title=payload.title or doc.title,
        content_text=payload.content_text,
        content_sha256=checksum(payload.content_text),
        source_kind=payload.source_kind,
        source_name=payload.source_name,
    )
    uow.session.add(row)
    uow.session.flush()
    return row


def create(uow: UnitOfWork, payload: NewDocument, request: Request) -> RevisionSummary:
    require_role(uow.scope, "admin", "manager")
    doc = Document(
        workspace_id=uow.scope.workspace_id, title=payload.title, created_by_member_id=member(uow)
    )
    uow.session.add(doc)
    uow.session.flush()
    row = insert_draft(uow, doc, payload, 1)
    audit(uow, request, "knowledge.document_created", doc, ["title", "revision"])
    return revision_view(row, doc)


def add(uow: UnitOfWork, identifier: UUID, payload: Draft, request: Request) -> RevisionSummary:
    require_role(uow.scope, "admin", "manager")
    doc = document(uow, identifier, lock=True)
    match_version(request, doc.version)
    if doc.archived_at:
        raise Fault(409, "document_archived", "This article has been archived.")
    previous = (
        uow.session.scalar(
            select(func.max(Revision.revision_number)).where(Revision.document_id == doc.id)
        )
        or 0
    )
    row = insert_draft(uow, doc, payload, previous + 1)
    doc.version += 1
    audit(uow, request, "knowledge.draft_created", row, ["revision"])
    return revision_view(row, doc)


def edit(uow: UnitOfWork, identifier: UUID, payload: DraftPatch, request: Request) -> RevisionView:
    require_role(uow.scope, "admin", "manager")
    initial = revision(uow, identifier)
    doc = document(uow, initial.document_id, lock=True)
    row = revision(uow, identifier, lock=True)
    match_version(request, row.version)
    if doc.archived_at or row.status != "draft":
        raise Fault(409, "draft_required", "Only a draft on an unarchived article can be changed.")
    if payload.title is not None:
        row.title = payload.title
        if doc.active_version_id is None:
            doc.title = payload.title
    if payload.content_text is not None:
        row.content_text = payload.content_text
        row.content_sha256 = checksum(payload.content_text)
    row.version += 1
    doc.version += 1
    audit(uow, request, "knowledge.draft_updated", row, list(payload.model_fields_set))
    uow.session.flush()
    return revision_detail(uow, row.id)


def index_job(uow: UnitOfWork, identifier: UUID, *, lock: bool = False) -> Job | None:
    query = select(Job).where(Job.dedupe_key == "knowledge:" + str(identifier))
    return uow.session.scalar(query.with_for_update() if lock else query)


def publication(row: Revision, doc: Document, job: Job) -> Publication:
    return Publication(
        revision=revision_view(row, doc),
        job_id=job.id,
        poll_url=f"/api/v1/knowledge/versions/{row.id}",
    )


def enqueue(
    uow: UnitOfWork, identifier: UUID, request: Request, *, retry: bool = False
) -> Publication:
    require_role(uow.scope, "admin", "manager")
    initial = revision(uow, identifier)
    doc = document(uow, initial.document_id, lock=True)
    if doc.archived_at:
        raise Fault(409, "document_archived", "This article has been archived.")
    row = revision(uow, identifier, lock=True)
    if retry:
        match_version(request, row.version)
        return publication(row, doc, retry_failed(uow, doc, row, request))

    replay, exists = idempotency.prepare(uow, request, Empty())
    if exists:
        job = uow.session.get(Job, replay.resource_id)
        assert job
        return publication(row, doc, job)
    match_version(request, row.version)
    if row.status != "draft":
        raise Fault(409, "draft_required", "This revision was already submitted for indexing.")
    row.status = "queued"
    row.published_by_member_id = member(uow)
    row.version += 1
    doc.pending_version_id = row.id
    doc.version += 1
    job = Job(
        workspace_id=doc.workspace_id,
        kind="knowledge_index",
        payload_json={"id": str(row.id)},
        dedupe_key="knowledge:" + str(row.id),
    )
    uow.session.add(job)
    uow.session.flush()
    idempotency.complete(replay, "knowledge_index", job.id, 202)
    audit(uow, request, "knowledge.publication_queued", row, ["status"])
    return publication(row, doc, job)


def retry_failed(uow: UnitOfWork, doc: Document, row: Revision, request: Request) -> Job:
    job = index_job(uow, row.id, lock=True)
    if (
        doc.archived_at
        or doc.pending_version_id != row.id
        or row.status != "failed"
        or not job
        or job.status != "failed"
    ):
        raise Fault(409, "retry_unavailable", "Only the current failed publication can be retried.")
    job.status = row.status = "queued"
    job.available_at = now()
    job.finished_at = job.last_error_code = row.error_code = None
    job.attempts = 0
    job.version += 1
    row.version += 1
    audit(uow, request, "knowledge.index_retried", row, ["status"])
    uow.session.flush()
    return job


def archive(uow: UnitOfWork, identifier: UUID, payload: Archive, request: Request) -> DocumentView:
    require_role(uow.scope, "admin", "manager")
    doc = document(uow, identifier, lock=True)
    match_version(request, doc.version)
    if doc.archived_at:
        return summaries(uow, [doc])[0]
    if doc.pending_version_id:
        row = revision(uow, doc.pending_version_id, lock=True)
        job = index_job(uow, row.id, lock=True)
        if job and job.status in {"queued", "running"}:
            row.status, row.error_code = "failed", "document_archived"
            row.version += 1
            job.status, job.last_error_code, job.finished_at = "failed", "document_archived", now()
            job.locked_by = job.attempt_token = job.lease_until = None
            job.version += 1
    doc.archived_at = now()
    doc.active_version_id = doc.pending_version_id = None
    doc.version += 1
    # Record the action and changed keys. Free-text reasons may contain source content.
    audit(
        uow, request, "knowledge.document_archived", doc, ["archived_at", *payload.model_fields_set]
    )
    uow.session.flush()
    return summaries(uow, [doc])[0]
