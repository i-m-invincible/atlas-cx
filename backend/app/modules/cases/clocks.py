"""Elapsed-time clocks shared by case projections and later reporting."""

from datetime import datetime, timedelta

from app.modules.cases.schemas import ClockView, State

ALLOWED: dict[str, set[str]] = {
    "triage": {"new"},
    "ask_customer": {"open"},
    "resume": {"pending_customer"},
    "resolve": {"new", "open", "pending_customer"},
    "reopen": {"resolved"},
    "close": {"resolved"},
}
DESTINATION: dict[str, State] = {
    "triage": "open",
    "ask_customer": "pending_customer",
    "resume": "open",
    "resolve": "resolved",
    "reopen": "open",
    "close": "closed",
}


def clock(
    opened_at: datetime,
    instant: datetime,
    target_seconds: int,
    paused_seconds: float = 0,
    pause_started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ClockView:
    end = finished_at or instant
    if (
        end < opened_at
        or paused_seconds < 0
        or (pause_started_at and not opened_at <= pause_started_at <= end)
    ):
        raise ValueError("Invalid clock timestamps")
    running_pause = (end - pause_started_at).total_seconds() if pause_started_at else 0
    active = (end - opened_at).total_seconds() - paused_seconds - running_pause
    if active < -0.000001:
        raise ValueError("Paused duration exceeds elapsed duration")
    active = max(0.0, active)
    overdue = active > target_seconds
    status = (
        ("missed" if overdue else "met")
        if finished_at
        else ("paused" if pause_started_at else "overdue" if overdue else "due")
    )
    return ClockView(
        status=status,
        elapsed_seconds=active,
        remaining_seconds=max(0.0, target_seconds - active),
        target_seconds=target_seconds,
        is_overdue=overdue,
        due_at=None
        if pause_started_at or finished_at
        else opened_at + timedelta(seconds=target_seconds + paused_seconds),
    )
