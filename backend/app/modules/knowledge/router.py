from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from python_multipart.exceptions import MultipartParseError
from sqlalchemy import func, select
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.types import Message

from app.modules.activities.schemas import PageFilters
from app.modules.cases.router import Staff, listing
from app.modules.identity.security import check_origin
from app.modules.knowledge import assistant, library, operations, retrieval
from app.modules.knowledge.content import MAX_UPLOAD, decode_upload
from app.modules.knowledge.schemas import (
    Answer,
    Archive,
    Availability,
    DocumentDetail,
    DocumentFilters,
    DocumentView,
    Draft,
    DraftPatch,
    FeedbackInput,
    JobFilters,
    JobView,
    NewDocument,
    Publication,
    Question,
    RevisionSummary,
    RevisionView,
    SearchFilters,
    Source,
)
from app.platform.config import get_settings
from app.platform.jobs import Job
from app.platform.protocol import Envelope, Fault, Meta, result

router = APIRouter(tags=["knowledge and assistant"])


def upload_schema(title: bool) -> dict[str, object]:
    fields = {"file": {"type": "string", "format": "binary"}}
    if title:
        fields["title"] = {"type": "string", "maxLength": "200"}
    return {
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {"type": "object", "required": list(fields), "properties": fields}
                }
            },
        }
    }


async def uploaded(request: Request) -> Draft:
    check_origin(request)
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "multipart/form-data"
    ):
        raise Fault(415, "invalid_upload", "Choose a TXT or Markdown file.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_UPLOAD + 8192:
            raise Fault(413, "document_too_large", "Choose a text file no larger than 1 MiB.")
        body.extend(chunk)

    async def receive() -> Message:
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    bounded = Request(request.scope, receive)
    try:
        async with bounded.form(max_files=1, max_fields=1, max_part_size=2048) as form:
            file = form.get("file")
            title = form.get("title")
            if not isinstance(file, UploadFile) or set(form.keys()) - {"file", "title"}:
                raise Fault(422, "file_required", "Choose one TXT or Markdown file.")
            if file.content_type in {"text/html", "application/pdf"}:
                raise Fault(415, "invalid_upload", "Choose a TXT or Markdown file.")
            raw = await file.read(MAX_UPLOAD + 1)
            if len(raw) > MAX_UPLOAD:
                raise Fault(413, "document_too_large", "Choose a text file no larger than 1 MiB.")
            content, kind, name = decode_upload(raw, file.filename or "")
            return Draft.model_validate(
                {"title": title, "content_text": content, "source_kind": kind, "source_name": name}
            )
    except (HTTPException, MultipartParseError, ValueError):
        raise Fault(
            422, "invalid_upload", "Use UTF-8 TXT or Markdown with 1 to 200,000 characters."
        ) from None


Upload = Annotated[Draft, Depends(uploaded)]


@router.get("/knowledge/documents")
def documents(
    filters: Annotated[DocumentFilters, Query()], request: Request, uow: Staff
) -> Envelope[list[DocumentView]]:
    return listing(request, *library.page_documents(uow, filters))


@router.get("/knowledge/documents/{identifier}")
def document(
    identifier: UUID,
    filters: Annotated[PageFilters, Query()],
    request: Request,
    response: Response,
    uow: Staff,
) -> Envelope[DocumentDetail]:
    doc, cursor = library.detail(uow, identifier, filters.cursor, filters.limit)
    response.headers["ETag"] = f'"{doc.version}"'
    return Envelope(
        data=doc,
        meta=Meta(
            request_id=request.state.request_id, next_cursor=cursor, has_more=cursor is not None
        ),
    )


def revision_created(
    request: Request, response: Response, row: RevisionSummary
) -> Envelope[RevisionSummary]:
    response.headers["Location"] = f"/api/v1/knowledge/versions/{row.id}"
    return result(request, row, response)


@router.post("/knowledge/documents", status_code=201)
def create(
    payload: NewDocument, request: Request, response: Response, uow: Staff
) -> Envelope[RevisionSummary]:
    return revision_created(request, response, library.create(uow, payload, request))


@router.post("/knowledge/documents/upload", status_code=201, openapi_extra=upload_schema(True))
def create_upload(
    payload: Upload, request: Request, response: Response, uow: Staff
) -> Envelope[RevisionSummary]:
    if not payload.title:
        raise Fault(422, "title_required", "Enter an article title.")
    draft = NewDocument.model_validate(payload.model_dump())
    return revision_created(request, response, library.create(uow, draft, request))


@router.post("/knowledge/documents/{identifier}/versions", status_code=201)
def create_revision(
    identifier: UUID, payload: Draft, request: Request, response: Response, uow: Staff
) -> Envelope[RevisionSummary]:
    return revision_created(request, response, library.add(uow, identifier, payload, request))


@router.post(
    "/knowledge/documents/{identifier}/upload-version",
    status_code=201,
    openapi_extra=upload_schema(False),
)
def upload_revision(
    identifier: UUID, payload: Upload, request: Request, response: Response, uow: Staff
) -> Envelope[RevisionSummary]:
    return revision_created(request, response, library.add(uow, identifier, payload, request))


@router.get("/knowledge/versions/{identifier}")
def version(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[RevisionView]:
    return result(request, library.revision_detail(uow, identifier), response)


@router.patch("/knowledge/versions/{identifier}")
def edit(
    identifier: UUID, payload: DraftPatch, request: Request, response: Response, uow: Staff
) -> Envelope[RevisionView]:
    return result(request, library.edit(uow, identifier, payload, request), response)


def accepted(
    request: Request, response: Response, publication: Publication
) -> Envelope[Publication]:
    response.headers["Location"] = publication.poll_url
    return result(request, publication)


@router.post("/knowledge/versions/{identifier}/publish", status_code=202)
def publish(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[Publication]:
    return accepted(request, response, library.enqueue(uow, identifier, request))


@router.post("/knowledge/versions/{identifier}/retry", status_code=202)
def retry_revision(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[Publication]:
    return accepted(request, response, library.enqueue(uow, identifier, request, retry=True))


@router.post("/knowledge/documents/{identifier}/archive")
def archive(
    identifier: UUID, payload: Archive, request: Request, response: Response, uow: Staff
) -> Envelope[DocumentView]:
    return result(request, library.archive(uow, identifier, payload, request), response)


@router.get("/knowledge/search")
def search(
    filters: Annotated[SearchFilters, Query()], request: Request, uow: Staff
) -> Envelope[list[Source]]:
    return listing(
        request,
        retrieval.lexical(uow.session, uow.scope.workspace_id, filters.q, filters.limit),
        None,
    )


@router.get("/knowledge/chunks/{identifier}")
def chunk(identifier: UUID, request: Request, uow: Staff) -> Envelope[Source]:
    return result(request, retrieval.inspect(uow.session, uow.scope.workspace_id, identifier))


@router.get("/knowledge/availability")
def availability(request: Request, uow: Staff) -> Envelope[Availability]:
    heartbeat = (
        uow.session.scalar(select(func.max(Job.heartbeat_at)).where(Job.kind == "knowledge_index"))
        if library.manager(uow)
        else None
    )
    return result(
        request,
        Availability(
            source_search=True,
            indexing_worker_seen_at=heartbeat,
            generation_configured=get_settings().generation_mode == "ollama",
        ),
    )


@router.post("/assistant/requests", status_code=202)
def ask(payload: Question, request: Request, response: Response, uow: Staff) -> Envelope[Answer]:
    answer = assistant.answer(uow, assistant.submit(uow, payload, request))
    response.headers["Location"] = answer.poll_url
    return result(request, answer)


@router.get("/assistant/requests/{identifier}")
def answer(identifier: UUID, request: Request, uow: Staff) -> Envelope[Answer]:
    return result(request, assistant.answer(uow, assistant.owned(uow, identifier)))


@router.put("/assistant/requests/{identifier}/feedback")
def rate(
    identifier: UUID, payload: FeedbackInput, request: Request, uow: Staff
) -> Envelope[Answer]:
    return result(request, assistant.feedback(uow, identifier, payload))


@router.get("/jobs")
def jobs(
    filters: Annotated[JobFilters, Query()], request: Request, uow: Staff
) -> Envelope[list[JobView]]:
    return listing(request, *operations.page(uow, filters))


@router.get("/jobs/{identifier}")
def job(identifier: UUID, request: Request, response: Response, uow: Staff) -> Envelope[JobView]:
    return result(request, operations.view(operations.get(uow, identifier)), response)


@router.post("/jobs/{identifier}/retry")
def retry_job(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[JobView]:
    return result(request, operations.retry(uow, identifier, request), response)
