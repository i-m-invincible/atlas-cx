from datetime import datetime
from uuid import UUID

from fastapi import Request
from sqlalchemy import select, tuple_

from app.modules.knowledge import library
from app.modules.knowledge.schemas import JobFilters, JobView
from app.platform.auth import UnitOfWork, require_role
from app.platform.jobs import Job
from app.platform.protocol import Fault, match_version, missing, read_cursor, sign_cursor


def view(row: Job) -> JobView:
    return JobView.model_validate(row, from_attributes=True)


def get(uow: UnitOfWork, identifier: UUID) -> Job:
    require_role(uow.scope, "admin", "manager")
    job = uow.session.get(Job, identifier)
    if not job:
        raise missing()
    return job


def page(uow: UnitOfWork, filters: JobFilters) -> tuple[list[JobView], str | None]:
    require_role(uow.scope, "admin", "manager")
    query = select(Job)
    if filters.kind:
        query = query.where(Job.kind == filters.kind)
    if filters.status:
        query = query.where(Job.status == filters.status)
    binding = {
        "workspace": str(uow.scope.workspace_id),
        "resource": "jobs",
        "kind": filters.kind,
        "status": filters.status,
    }
    if filters.cursor:
        try:
            stamp, identifier = read_cursor(filters.cursor, binding)
            query = query.where(
                tuple_(Job.created_at, Job.id) < (datetime.fromisoformat(stamp), UUID(identifier))
            )
        except ValueError:
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    rows = list(
        uow.session.scalars(
            query.order_by(Job.created_at.desc(), Job.id.desc()).limit(filters.limit + 1)
        )
    )
    more = len(rows) > filters.limit
    rows = rows[: filters.limit]
    cursor = (
        sign_cursor(binding, [rows[-1].created_at.isoformat(), str(rows[-1].id)]) if more else None
    )
    return [view(row) for row in rows], cursor


def retry(uow: UnitOfWork, identifier: UUID, request: Request) -> JobView:
    job = get(uow, identifier)
    if job.kind != "knowledge_index":
        raise Fault(409, "retry_unavailable", "Submit a new assistant question.")
    target = library.revision(uow, UUID(job.payload_json["id"]))
    doc = library.document(uow, target.document_id, lock=True)
    target = library.revision(uow, target.id, lock=True)
    match_version(request, job.version)
    return view(library.retry_failed(uow, doc, target, request))
