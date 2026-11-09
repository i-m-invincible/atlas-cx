from datetime import timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.modules.cases.repository import get_case
from app.modules.knowledge.model_manifest import PROMPT_VERSION
from app.modules.knowledge.models import AssistantFeedback, AssistantRequest, Citation
from app.modules.knowledge.retrieval import RETRIEVAL_VERSION, sources_by_id, valid_excerpt
from app.modules.knowledge.schemas import Answer, AssistantSource, FeedbackInput, Question
from app.platform import idempotency
from app.platform.auth import UnitOfWork, require_role
from app.platform.config import get_settings
from app.platform.jobs import Job
from app.platform.protocol import Fault, missing, now
from app.platform.rate_limits import RateBucket

WAIT_NOTICE = timedelta(seconds=30)
REQUEST_LIMIT = timedelta(minutes=5)
RETENTION = timedelta(days=30)
QUESTION_ROLES = ("admin", "manager", "agent")


def owned(uow: UnitOfWork, identifier: UUID) -> AssistantRequest:
    require_role(uow.scope, *QUESTION_ROLES)
    row = uow.session.get(AssistantRequest, identifier)
    if not row or row.requested_by_member_id != uow.scope.member_id or row.expires_at <= now():
        raise missing()
    return row


def question_budget(uow: UnitOfWork, member_id: UUID) -> None:
    settings = get_settings()
    instant = now()
    minute = instant.replace(second=0, microsecond=0)
    day = instant.replace(hour=0, minute=0, second=0, microsecond=0)
    for principal, operation, start, limit, seconds in (
        (str(member_id), "assistant.minute", minute, settings.assistant_per_member_per_minute, 60),
        ("workspace", "assistant.day", day, settings.assistant_per_workspace_per_day, 86400),
    ):
        statement = insert(RateBucket).values(
            workspace_id=uow.scope.workspace_id,
            principal_key=principal,
            operation=operation,
            window_start=start,
            request_count=1,
        )
        count = uow.session.scalar(
            statement.on_conflict_do_update(
                index_elements=["workspace_id", "principal_key", "operation", "window_start"],
                set_={"request_count": RateBucket.request_count + 1},
            ).returning(RateBucket.request_count)
        )
        if count is not None and count > limit:
            retry = int((start + timedelta(seconds=seconds) - instant).total_seconds()) + 1
            raise Fault(
                429,
                "assistant_rate_limit",
                "The question limit has been reached.",
                {"Retry-After": str(retry)},
            )


def submit(uow: UnitOfWork, payload: Question, request: Request) -> AssistantRequest:
    require_role(uow.scope, *QUESTION_ROLES)
    if payload.case_id:
        get_case(uow, payload.case_id)
    replay, exists = idempotency.prepare(uow, request, payload)
    if exists:
        assert replay.resource_id
        return owned(uow, replay.resource_id)
    member_id = uow.scope.member_id
    assert member_id
    instant = now()
    pending = uow.session.scalar(
        select(func.count(AssistantRequest.id)).where(
            AssistantRequest.requested_by_member_id == member_id,
            AssistantRequest.state.in_(["queued", "running"]),
            AssistantRequest.created_at > instant - REQUEST_LIMIT,
        )
    )
    if pending is not None and pending >= 2:
        raise Fault(
            429,
            "assistant_pending_limit",
            "Wait for a pending question to finish.",
            {"Retry-After": "5"},
        )
    question_budget(uow, member_id)
    row = AssistantRequest(
        workspace_id=uow.scope.workspace_id,
        requested_by_member_id=member_id,
        requested_by_session_id=uow.scope.session_id,
        question=payload.question,
        case_id=payload.case_id,
        expires_at=instant + RETENTION,
        prompt_version=PROMPT_VERSION,
        retrieval_version=RETRIEVAL_VERSION,
    )
    uow.session.add(row)
    uow.session.flush()
    uow.session.add(
        Job(
            workspace_id=row.workspace_id,
            kind="assistant_request",
            payload_json={"id": str(row.id)},
            dedupe_key="assistant:" + str(row.id),
        )
    )
    idempotency.complete(replay, "assistant_request", row.id, 202)
    return row


def answer(uow: UnitOfWork, row: AssistantRequest) -> Answer:
    # The authenticated UoW holds the workspace lock through the read. Publication
    # and archival use the same lock, so a result has one consistent source view.
    citations = (
        list(
            uow.session.scalars(
                select(Citation).where(Citation.request_id == row.id).order_by(Citation.rank)
            )
        )
        if row.source_count
        else []
    )
    current = sources_by_id(uow.session, row.workspace_id, [item.chunk_id for item in citations])
    sources = []
    for item in citations:
        source = current.get(item.chunk_id)
        if source is None or item.excerpt is None:
            continue
        cited = AssistantSource(
            **source.model_dump(exclude={"excerpt", "start_offset", "end_offset"}),
            excerpt=item.excerpt,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            label=item.label,
            rank=item.rank,
        )
        if valid_excerpt(cited, source):
            sources.append(cited)
    changed = len(sources) != row.source_count or row.error_code == "sources_changed"
    instant = now()
    timed_out = row.state in {"queued", "running"} and row.created_at + REQUEST_LIMIT <= instant
    helpful = uow.session.scalar(
        select(AssistantFeedback.helpful).where(AssistantFeedback.request_id == row.id)
    )
    return Answer.model_validate(
        {
            "id": row.id,
            "state": "failed" if timed_out else row.state,
            "mode": "sources_only" if changed else row.mode,
            "answer_text": None if changed else row.answer_text,
            "abstention_reason": None if changed else row.abstention_reason,
            "error_code": (
                "sources_changed" if changed else "request_expired" if timed_out else row.error_code
            ),
            "sources": sources,
            "model_id": None if changed else row.model_id,
            "case_id": row.case_id,
            "delayed": row.state == "queued"
            and WAIT_NOTICE <= instant - row.created_at < REQUEST_LIMIT,
            "completed_at": row.completed_at,
            "created_at": row.created_at,
            "poll_url": f"/api/v1/assistant/requests/{row.id}",
            "feedback": helpful,
        }
    )


def feedback(uow: UnitOfWork, identifier: UUID, payload: FeedbackInput) -> Answer:
    row = owned(uow, identifier)
    if row.state != "completed":
        raise Fault(409, "answer_pending", "Wait for this question to finish before rating it.")
    statement = insert(AssistantFeedback).values(
        workspace_id=row.workspace_id,
        request_id=row.id,
        member_id=row.requested_by_member_id,
        helpful=payload.helpful,
        reason=payload.reason,
    )
    uow.session.execute(
        statement.on_conflict_do_update(
            index_elements=["workspace_id", "request_id", "member_id"],
            set_={"helpful": payload.helpful, "reason": payload.reason},
        )
    )
    return answer(uow, row)
