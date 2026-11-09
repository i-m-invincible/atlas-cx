from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.types import Message

from app.modules.cases.router import Staff
from app.modules.customers import import_service as service
from app.modules.customers.import_schemas import ImportView
from app.modules.identity.security import check_origin
from app.platform.errors import problem_response
from app.platform.protocol import Envelope, Fault, result

router = APIRouter(tags=["customer imports"])


async def read_upload(request: Request) -> bytes:
    check_origin(request)
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "multipart/form-data"
    ):
        raise Fault(415, "invalid_upload", "Upload the CSV using the file field.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > service.MAX_BYTES + 8192:
            raise Fault(413, "csv_too_large", "Choose a CSV file no larger than 1 MiB.")
        data.extend(chunk)

    async def receive() -> Message:
        return {"type": "http.request", "body": bytes(data), "more_body": False}

    bounded = Request(request.scope, receive)
    try:
        async with bounded.form(max_files=1, max_fields=0) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile):
                raise Fault(422, "file_required", "Choose a CSV file.")
            return await file.read(service.MAX_BYTES + 1)
    except (HTTPException, MultipartParseError):
        raise Fault(422, "invalid_upload", "Upload one CSV file using the file field.") from None


@router.post(
    "/customer-imports/validate",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {
                            "file": {"type": "string", "format": "binary"},
                        },
                    }
                }
            },
        }
    },
)
def validate(
    contents: Annotated[bytes, Depends(read_upload)],
    request: Request,
    response: Response,
    uow: Staff,
) -> Envelope[ImportView]:
    row = service.stage(uow, contents, request)
    response.headers["Location"] = f"/api/v1/customer-imports/{row.id}"
    return result(request, service.view(row), response)


@router.get("/customer-imports/{identifier}")
def detail(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[ImportView]:
    return result(request, service.view(service.get(uow, identifier)), response)


@router.post("/customer-imports/{identifier}/commit", response_model=Envelope[ImportView])
def commit(
    identifier: UUID, request: Request, response: Response, uow: Staff
) -> Envelope[ImportView] | Response:
    row, fault = service.commit(uow, identifier, request)
    if fault:
        return problem_response(request, fault.status, fault.code, fault.detail)
    return result(request, service.view(row), response)
