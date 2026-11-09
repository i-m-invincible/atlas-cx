"""Queue-only claims and heartbeats. Business completion uses a scoped app session."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine, case, select, update
from sqlalchemy.orm import Session

from app.platform.jobs import Job
from app.platform.protocol import now

LEASE = timedelta(seconds=120)
PROCESSING_SECONDS = 90
HEARTBEAT_SECONDS = 15
MAX_ATTEMPTS = 4


@dataclass(frozen=True)
class Attempt:
    id: UUID
    workspace_id: UUID
    target_id: UUID
    kind: str
    owner: str
    token: UUID
    number: int


def claim(engine: Engine, owner: str, prefer_index: bool = False) -> Attempt | None:
    instant = now()
    index = Job.kind == "knowledge_index"
    waiting = (Job.status == "queued") & (Job.available_at <= instant)
    lost_index = index & (Job.status == "running") & (Job.lease_until <= instant)
    live = index | (Job.created_at > instant - timedelta(minutes=5))
    priority = case((index, 0 if prefer_index else 1), else_=1 if prefer_index else 0)
    with Session(engine) as db, db.begin():
        job = db.scalar(
            select(Job)
            .where(
                (waiting | lost_index) & live,
                Job.attempts < case((index, MAX_ATTEMPTS), else_=1),
            )
            .order_by(priority, Job.available_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if not job:
            return None
        token = uuid4()
        job.status, job.locked_by, job.attempt_token = "running", owner, token
        job.heartbeat_at, job.lease_until = instant, instant + LEASE
        job.attempts += 1
        job.version += 1
        return Attempt(
            job.id,
            job.workspace_id,
            UUID(job.payload_json["id"]),
            job.kind,
            owner,
            token,
            job.attempts,
        )


def heartbeat(engine: Engine, attempt: Attempt) -> None:
    instant = now()
    with Session(engine) as db, db.begin():
        db.execute(
            update(Job)
            .where(
                Job.id == attempt.id,
                Job.status == "running",
                Job.locked_by == attempt.owner,
                Job.attempt_token == attempt.token,
                Job.lease_until > instant,
            )
            .values(heartbeat_at=instant, lease_until=instant + LEASE)
        )


def held(db: Session, attempt: Attempt, *, lock: bool = False) -> Job | None:
    query = select(Job).where(
        Job.id == attempt.id,
        Job.workspace_id == attempt.workspace_id,
        Job.status == "running",
        Job.locked_by == attempt.owner,
        Job.attempt_token == attempt.token,
        Job.lease_until > now(),
    )
    return db.scalar(query.with_for_update() if lock else query)


def finish(
    job: Job,
    *,
    error: str | None = None,
    refs: dict[str, str] | None = None,
    retry_after: float | None = None,
) -> None:
    instant = now()
    job.status = "queued" if retry_after is not None else "failed" if error else "succeeded"
    if retry_after is not None:
        job.available_at = instant + timedelta(seconds=retry_after)
    job.finished_at = instant if retry_after is None else None
    job.last_error_code = error
    job.result_refs_json = refs
    job.locked_by = job.attempt_token = job.lease_until = None
    job.version += 1
