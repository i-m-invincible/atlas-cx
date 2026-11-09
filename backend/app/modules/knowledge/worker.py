"""AI and maintenance process entry points. The HTTP process only enqueues work."""

import argparse
import logging
import math
import random
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from threading import Event, Thread
from time import monotonic, sleep
from uuid import UUID, uuid4

from sqlalchemy import Engine, and_, delete, func, or_, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.identity.models import LoginSession, Membership, User
from app.modules.knowledge import retrieval
from app.modules.knowledge.assistant import QUESTION_ROLES, REQUEST_LIMIT
from app.modules.knowledge.content import checksum, split
from app.modules.knowledge.model_manifest import (
    EMBEDDING_REVISION,
    GENERATION_DIGEST,
    QWEN_TOKENIZER,
)
from app.modules.knowledge.models import (
    AssistantFeedback,
    AssistantRequest,
    Chunk,
    Citation,
    Document,
    Revision,
)
from app.modules.knowledge.providers import (
    EmbeddingProvider,
    FastTokenizer,
    GenerationProvider,
    MiniLM,
    ModelFailure,
    Ollama,
)
from app.modules.knowledge.schemas import AssistantSource
from app.modules.workspace.models import Workspace
from app.platform.audit import record_audit
from app.platform.config import Settings, get_settings
from app.platform.database import build_engine, set_scope, workspace_session
from app.platform.dispatch import (
    HEARTBEAT_SECONDS,
    MAX_ATTEMPTS,
    PROCESSING_SECONDS,
    Attempt,
    claim,
    finish,
    heartbeat,
    held,
)
from app.platform.jobs import Job
from app.platform.protocol import now
from app.platform.rate_limits import RateBucket

logger = logging.getLogger("atlas.worker")
MAX_DOCUMENTS = 500
MAX_CHUNKS = 10_000


@dataclass(frozen=True)
class Runtime:
    embedding: EmbeddingProvider | None
    count: Callable[[str], int]
    generation: GenerationProvider | None


def byte_budget(value: str) -> int:
    return len(value.encode("utf-8"))


def load_models(settings: Settings) -> Runtime:
    embedding = None
    tokenizer = None
    generation = None
    try:
        if settings.embedding_model_revision == EMBEDDING_REVISION:
            embedding = MiniLM(settings.model_directory)
    except Exception:
        logger.info("embedding_artifact_unavailable")
    try:
        tokenizer = FastTokenizer(settings.model_directory, QWEN_TOKENIZER)
    except Exception:
        logger.info("generation_tokenizer_unavailable")
    if (
        tokenizer
        and settings.generation_mode == "ollama"
        and settings.generation_model_digest == GENERATION_DIGEST
    ):
        try:
            generation = Ollama(settings.ollama_base_url, tokenizer)
        except (ValueError, ModelFailure):
            logger.info("generation_unavailable")
    return Runtime(embedding, tokenizer.count if tokenizer else byte_budget, generation)


def workspace_lock(db: Session, workspace_id: UUID) -> Workspace | None:
    return db.get(Workspace, workspace_id, with_for_update={"key_share": True})


def audit_worker(db: Session, attempt: Attempt, action: str, identifier: UUID) -> None:
    record_audit(
        db,
        attempt.workspace_id,
        None,
        action,
        "knowledge_version",
        identifier,
        ["status"],
        str(attempt.id),
        actor_kind="system",
    )


def index_rows(db: Session, attempt: Attempt) -> tuple[Job, Revision, Document] | None:
    workspace = workspace_lock(db, attempt.workspace_id)
    job = held(db, attempt, lock=True)
    if not job:
        return None
    row = db.get(Revision, attempt.target_id)
    doc = db.get(Document, row.document_id, with_for_update=True) if row else None
    if (
        not workspace
        or workspace.archived_at
        or not row
        or not doc
        or doc.archived_at
        or doc.pending_version_id != row.id
        or row.status not in {"queued", "indexing"}
    ):
        if row and row.status in {"queued", "indexing"}:
            row.status, row.error_code = "failed", "publication_superseded"
            row.version += 1
        finish(job, error="publication_superseded")
        return None
    return job, row, doc


def fail_index(engine: Engine, attempt: Attempt, code: str, transient: bool = False) -> None:
    with workspace_session(engine, attempt.workspace_id, "worker") as db:
        current = index_rows(db, attempt)
        if not current:
            return
        job, row, _ = current
        delay = None
        if transient and attempt.number < MAX_ATTEMPTS:
            delay = (5, 30, 120)[attempt.number - 1] + random.uniform(0, 2)
        row.status = "queued" if delay is not None else "failed"
        row.error_code = code
        row.version += 1
        finish(job, error=code, retry_after=delay)
        if delay is None:
            audit_worker(db, attempt, "knowledge.index_failed", row.id)


def index(engine: Engine, attempt: Attempt, runtime: Runtime, deadline: float) -> None:
    with workspace_session(engine, attempt.workspace_id, "worker") as db:
        current = index_rows(db, attempt)
        if not current:
            return
        _, row, _ = current
        row.status, row.error_code = "indexing", None
        row.version += 1
        canonical, sha = row.content_text, row.content_sha256
    if runtime.embedding is None:
        fail_index(engine, attempt, "embedding_unavailable")
        return
    try:
        passages = split(canonical, runtime.embedding.tokenizer)
    except ValueError:
        fail_index(engine, attempt, "invalid_index_text")
        return
    if len(passages) > MAX_CHUNKS:
        fail_index(engine, attempt, "capacity_exceeded")
        return
    try:
        vectors = runtime.embedding.embed([item.encoder_text for item in passages])
    except Exception:
        fail_index(engine, attempt, "embedding_failed", transient=True)
        return
    if monotonic() > deadline:
        fail_index(engine, attempt, "index_timeout", transient=True)
        return
    if len(vectors) != len(passages) or any(
        len(vector) != 384
        or not all(math.isfinite(value) for value in vector)
        or not math.isclose(math.sqrt(sum(value * value for value in vector)), 1, rel_tol=1e-4)
        for vector in vectors
    ):
        fail_index(engine, attempt, "invalid_embedding")
        return
    with workspace_session(engine, attempt.workspace_id, "worker") as db:
        current = index_rows(db, attempt)
        if not current:
            return
        job, row, doc = current
        active_others = select(Document.active_version_id).where(
            Document.id != doc.id,
            Document.archived_at.is_(None),
            Document.active_version_id.is_not(None),
        )
        documents = db.scalar(select(func.count()).select_from(active_others.subquery())) or 0
        chunks = (
            db.scalar(select(func.count(Chunk.id)).where(Chunk.version_id.in_(active_others))) or 0
        )
        if documents + 1 > MAX_DOCUMENTS or chunks + len(passages) > MAX_CHUNKS:
            row.status, row.error_code = "failed", "capacity_exceeded"
            row.version += 1
            finish(job, error=row.error_code)
            audit_worker(db, attempt, "knowledge.index_failed", row.id)
            return
        if (
            checksum(row.content_text) != sha
            or row.content_sha256 != sha
            or any(
                canonical[passage.start : passage.end] != passage.content for passage in passages
            )
        ):
            row.status, row.error_code = "failed", "revision_changed"
            row.version += 1
            finish(job, error=row.error_code)
            audit_worker(db, attempt, "knowledge.index_failed", row.id)
            return
        db.execute(delete(Chunk).where(Chunk.version_id == row.id))
        db.add_all(
            [
                Chunk(
                    workspace_id=row.workspace_id,
                    version_id=row.id,
                    ordinal=passage.ordinal,
                    heading_path=list(passage.heading_path),
                    start_offset=passage.start,
                    end_offset=passage.end,
                    content=passage.content,
                    token_count=passage.token_count,
                    embedding=vector,
                    embedding_model_revision=EMBEDDING_REVISION,
                )
                for passage, vector in zip(passages, vectors, strict=True)
            ]
        )
        db.flush()
        stored = db.scalar(select(func.count(Chunk.id)).where(Chunk.version_id == row.id))
        if stored != len(passages):
            raise ModelFailure("incomplete_index")
        row.status, row.indexed_at, row.embedding_model_revision = (
            "ready",
            now(),
            EMBEDDING_REVISION,
        )
        row.version += 1
        doc.active_version_id, doc.pending_version_id, doc.title = row.id, None, row.title
        doc.version += 1
        finish(job, refs={"revision_id": str(row.id)})
        audit_worker(db, attempt, "knowledge.indexed", row.id)


def requester_active(db: Session, row: AssistantRequest) -> bool:
    # Existing identity RLS has a staff audience. This internal read is scoped
    # to the leased workspace and never accepts identity from a job payload.
    set_scope(db, row.workspace_id, "staff")
    try:
        member = db.get(Membership, row.requested_by_member_id)
        stored = db.get(LoginSession, row.requested_by_session_id)
        user = db.get(User, member.user_id) if member else None
        instant = now()
        return bool(
            member
            and member.active
            and member.setup_completed_at
            and member.role in QUESTION_ROLES
            and user
            and not user.disabled_at
            and stored
            and stored.user_id == member.user_id
            and stored.workspace_id == row.workspace_id
            and stored.audience == "staff"
            and not stored.revoked_at
            and stored.expires_at > instant
            and stored.absolute_expires_at > instant
        )
    finally:
        set_scope(db, row.workspace_id, "worker")


def fail_assistant(job: Job, row: AssistantRequest | None, code: str) -> None:
    if row and row.state in {"queued", "running"}:
        row.state, row.error_code, row.completed_at = "failed", code, now()
        row.answer_text = None
    finish(job, error=code)


def assistant_rows(db: Session, attempt: Attempt) -> tuple[Job, AssistantRequest] | None:
    workspace = workspace_lock(db, attempt.workspace_id)
    job = held(db, attempt, lock=True)
    if not job:
        return None
    row = db.get(AssistantRequest, attempt.target_id, with_for_update=True)
    if not row or not workspace or workspace.archived_at or not requester_active(db, row):
        fail_assistant(job, row, "requester_unavailable")
        return None
    if row.created_at + REQUEST_LIMIT <= now() or not row.question:
        fail_assistant(job, row, "request_expired")
        return None
    return job, row


def ask(engine: Engine, attempt: Attempt, runtime: Runtime, deadline: float) -> None:
    with workspace_session(engine, attempt.workspace_id, "worker") as db:
        current = assistant_rows(db, attempt)
        if not current:
            return
        _, row = current
        row.state = "running"
        question = row.question
        assert question
    vector = None
    if runtime.embedding is not None:
        try:
            vector = runtime.embedding.embed([question])[0]
        except Exception:
            logger.info("query_embedding_unavailable job=%s", attempt.id)
    retrieval_start = monotonic()
    with workspace_session(engine, attempt.workspace_id, "worker") as db:
        if not assistant_rows(db, attempt):
            return
        lexical = retrieval.lexical(db, attempt.workspace_id, question)
        vectors = (
            retrieval.vector(db, attempt.workspace_id, question, vector, EMBEDDING_REVISION)
            if vector
            else []
        )
        selected = retrieval.evidence(retrieval.rank(lexical, vectors, "hybrid"), runtime.count)
    retrieval_ms = round((monotonic() - retrieval_start) * 1000)
    mode = "sources_only" if selected else "abstained"
    reason = None if selected else "insufficient_evidence"
    error = "embedding_unavailable" if selected and vector is None else None
    answer = model = None
    generation_ms = input_tokens = output_tokens = None
    if selected and vector is not None:
        if runtime.generation and deadline - monotonic() >= 65:
            started = monotonic()
            try:
                generated = runtime.generation.generate(question, selected)
                answer, reason, model = generated.answer, generated.reason, generated.model
                mode = "generated" if answer else "abstained"
                input_tokens, output_tokens = generated.input_tokens, generated.output_tokens
            except ModelFailure as exc:
                error = exc.code
            except Exception:
                error = "generation_unavailable"
            generation_ms = round((monotonic() - started) * 1000)
        else:
            error = "generation_unavailable"
    with workspace_session(engine, attempt.workspace_id, "worker") as db:
        current = assistant_rows(db, attempt)
        if not current:
            return
        job, row = current
        if monotonic() > deadline:
            fail_assistant(job, row, "processing_timeout")
            return
        approved = retrieval.sources_by_id(
            db, row.workspace_id, [item.chunk_id for item in selected]
        )
        checked = {
            item.chunk_id: current_source is not None
            and retrieval.valid_excerpt(item, current_source)
            for item in selected
            if (current_source := approved.get(item.chunk_id)) is not None
        }
        if not all(checked.get(item.chunk_id, False) for item in selected):
            answer = reason = model = None
            mode, error = "sources_only", "sources_changed"
        store_citations(db, row, selected, checked)
        row.state, row.mode, row.answer_text = "completed", mode, answer
        row.abstention_reason, row.model_id, row.error_code = reason, model, error
        row.source_count = len(selected)
        row.completed_at = now()
        finish(job, refs={"request_id": str(row.id)})
    logger.info(
        "assistant_result job=%s mode=%s error=%s retrieval_ms=%s generation_ms=%s "
        "input_tokens=%s output_tokens=%s model=%s retrieval=%s",
        attempt.id,
        mode,
        error,
        retrieval_ms,
        generation_ms,
        input_tokens,
        output_tokens,
        model,
        retrieval.RETRIEVAL_VERSION,
    )


def store_citations(
    db: Session,
    row: AssistantRequest,
    sources: list[AssistantSource],
    checked: dict[UUID, bool],
) -> None:
    db.add_all(
        [
            Citation(
                workspace_id=row.workspace_id,
                request_id=row.id,
                label=item.label,
                document_id=item.document_id,
                version_id=item.version_id,
                chunk_id=item.chunk_id,
                excerpt=item.excerpt if checked.get(item.chunk_id) else None,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                rank=item.rank,
            )
            for item in sources
        ]
    )


def process(app: Engine, queue: Engine, attempt: Attempt, runtime: Runtime) -> None:
    started = monotonic()
    stop = Event()

    def renew() -> None:
        while not stop.wait(HEARTBEAT_SECONDS) and monotonic() - started < PROCESSING_SECONDS:
            try:
                heartbeat(queue, attempt)
            except SQLAlchemyError:
                logger.info("job_heartbeat_failed job=%s", attempt.id)

    thread = Thread(target=renew, daemon=True)
    thread.start()
    try:
        operation = index if attempt.kind == "knowledge_index" else ask
        operation(app, attempt, runtime, started + PROCESSING_SECONDS)
    except Exception:
        if attempt.kind == "knowledge_index":
            fail_index(app, attempt, "indexing_failed", transient=True)
        else:
            with workspace_session(app, attempt.workspace_id, "worker") as db:
                current = assistant_rows(db, attempt)
                if current:
                    fail_assistant(*current, "assistant_failed")
    finally:
        stop.set()
        thread.join()
        logger.info(
            "job_finished job=%s kind=%s attempt=%s duration_ms=%s",
            attempt.id,
            attempt.kind,
            attempt.number,
            round((monotonic() - started) * 1000),
        )


def maintenance(app: Engine, queue: Engine) -> None:
    instant = now()
    with queue.connect() as scheduler:
        if not scheduler.scalar(text("SELECT pg_try_advisory_lock(27370511)")):
            return
        try:
            candidates = scheduler.execute(
                select(Job.workspace_id, Job.id)
                .where(
                    Job.status.in_(["queued", "running"]),
                    or_(
                        and_(
                            Job.kind == "assistant_request",
                            or_(
                                Job.created_at <= instant - REQUEST_LIMIT,
                                and_(Job.status == "running", Job.lease_until <= instant),
                            ),
                        ),
                        and_(
                            Job.kind == "knowledge_index",
                            Job.status == "running",
                            Job.lease_until <= instant,
                            Job.attempts >= MAX_ATTEMPTS,
                        ),
                    ),
                )
                .order_by(Job.created_at)
                .limit(200)
            ).all()
            for workspace, identifier in candidates:
                with workspace_session(app, workspace, "worker") as db:
                    workspace_lock(db, workspace)
                    job = db.get(Job, identifier, with_for_update=True)
                    if not job or job.status not in {"queued", "running"}:
                        continue
                    target = UUID(job.payload_json["id"])
                    expired = job.lease_until is not None and job.lease_until <= now()
                    if job.kind == "assistant_request" and (
                        expired or job.created_at + REQUEST_LIMIT <= now()
                    ):
                        fail_assistant(job, db.get(AssistantRequest, target), "request_expired")
                    elif job.kind == "knowledge_index" and expired and job.attempts >= MAX_ATTEMPTS:
                        revision = db.get(Revision, target)
                        if revision and revision.status in {"queued", "indexing"}:
                            revision.status, revision.error_code = "failed", "lease_expired"
                            revision.version += 1
                        finish(job, error="lease_expired")
            workspaces = list(scheduler.scalars(select(Job.workspace_id).distinct()))
            for workspace in workspaces:
                with workspace_session(app, workspace, "worker") as db:
                    expired_ids = select(AssistantRequest.id).where(
                        AssistantRequest.expires_at <= instant
                    )
                    db.execute(
                        update(Citation)
                        .where(Citation.request_id.in_(expired_ids), Citation.excerpt.is_not(None))
                        .values(excerpt=None)
                    )
                    db.execute(
                        update(AssistantFeedback)
                        .where(
                            AssistantFeedback.request_id.in_(expired_ids),
                            AssistantFeedback.reason.is_not(None),
                        )
                        .values(reason=None)
                    )
                    db.execute(
                        update(AssistantRequest)
                        .where(
                            AssistantRequest.expires_at <= instant,
                            AssistantRequest.question.is_not(None),
                        )
                        .values(question=None, answer_text=None, case_id=None)
                    )
                    db.execute(
                        delete(RateBucket).where(
                            RateBucket.operation.in_(["assistant.minute", "assistant.day"]),
                            RateBucket.window_start < instant - timedelta(days=2),
                        )
                    )
        finally:
            scheduler.execute(text("SELECT pg_advisory_unlock(27370511)"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=["ai", "core"])
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    queue = build_engine(settings.queue_database_url.get_secret_value())
    app = build_engine(settings.database_url.get_secret_value())
    owner = socket.gethostname()[:60] + "-" + uuid4().hex
    runtime = load_models(settings) if args.role == "ai" else Runtime(None, byte_budget, None)
    count = 0
    try:
        while True:
            try:
                if args.role == "core":
                    maintenance(app, queue)
                else:
                    job = claim(queue, owner, prefer_index=count % 4 == 3)
                    if job:
                        process(app, queue, job, runtime)
                        count += 1
                        if not args.once:
                            continue
            except SQLAlchemyError:
                logger.warning("worker_database_unavailable role=%s", args.role)
                if args.once:
                    raise SystemExit(1) from None
            if args.once:
                break
            sleep(60 if args.role == "core" else 1)
    finally:
        queue.dispose()
        app.dispose()


if __name__ == "__main__":
    main()
