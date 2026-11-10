from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette.types import Message

from app.modules.activities.schemas import EventBatch, IngestResult
from app.modules.activities.service import MAX_BODY_BYTES, ingest_batch, invalid_credential
from app.platform.errors import problem_response
from app.platform.protocol import Envelope, Fault, result


class BoundedBatchRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handle = super().get_route_handler()

        async def bounded(request: Request) -> Response:
            if (
                request.headers.get("content-type", "").split(";", 1)[0].lower()
                != "application/json"
            ):
                raise Fault(415, "invalid_content_type", "Send the event batch as JSON.")
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    raise Fault(413, "batch_too_large", "Event batches may contain at most 1 MiB.")
                body.extend(chunk)

            async def receive() -> Message:
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            return await handle(Request(request.scope, receive))

        return bounded


router = APIRouter(tags=["event ingestion"], route_class=BoundedBatchRoute)
Bearer = Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))]


@router.post("/events/batch", response_model=Envelope[IngestResult])
def batch(
    payload: EventBatch, request: Request, authorization: Bearer
) -> Envelope[IngestResult] | Response:
    if authorization is None:
        raise invalid_credential()
    with Session(request.app.state.engine) as session, session.begin():
        outcome = ingest_batch(session, authorization.credentials, payload)
    if isinstance(outcome, Fault):
        return problem_response(
            request, outcome.status, outcome.code, outcome.detail, headers=outcome.headers
        )
    return result(request, outcome)
