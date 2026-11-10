import csv
import io
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.analytics import repository
from app.modules.analytics.schemas import (
    Bucket,
    CategoryVolume,
    Durations,
    ExportFilters,
    MetricRecord,
    Overview,
    Rate,
    RecordFilters,
    ReportFilters,
    ReportScope,
    TrendPoint,
    Trends,
)
from app.modules.identity.repository import authenticate
from app.modules.identity.security import SESSION_COOKIE
from app.modules.workspace.models import Workspace
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role, staff_uow
from app.platform.database import set_scope
from app.platform.protocol import Fault, read_cursor, sign_cursor


def report_uow(request: Request) -> Iterator[UnitOfWork]:
    # Preserve ordinary idle-session refresh, then recheck the session and
    # membership in the report snapshot without locking mutable identity rows.
    for _ in staff_uow(request):
        pass
    raw = request.cookies.get(SESSION_COOKIE, "")
    with Session(request.app.state.engine) as session, session.begin():
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        scope, _ = authenticate(session, raw, refresh=False)
        require_role(scope, "admin", "manager", "agent", "viewer")
        set_scope(session, scope.workspace_id, scope.audience, scope.user_id)
        request.state.principal = scope
        yield UnitOfWork(session, scope)


def boundary(value: str | None, fallback: date, zone: ZoneInfo) -> datetime:
    if value is None:
        return datetime.combine(fallback, time.min, zone)
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), time.min, zone)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("A report timestamp needs an offset")
    return parsed.astimezone(zone)


def report_scope(uow: UnitOfWork, filters: ReportFilters) -> ReportScope:
    instant = uow.session.scalar(text("SELECT transaction_timestamp()"))
    workspace = uow.session.get(Workspace, uow.scope.workspace_id)
    assert workspace and isinstance(instant, datetime)
    timezone = filters.timezone or workspace.timezone
    try:
        zone = ZoneInfo(timezone)
        today = instant.astimezone(zone).date()
        start = boundary(filters.from_, today - timedelta(days=29), zone)
        end = boundary(filters.to, today + timedelta(days=1), zone)
        if start.astimezone(UTC) >= end.astimezone(UTC) or end.replace(tzinfo=None) - start.replace(
            tzinfo=None
        ) > timedelta(days=366):
            raise ValueError("Out of range")
    except (ValueError, OverflowError, ZoneInfoNotFoundError):
        raise Fault(
            422,
            "invalid_report_scope",
            "Use a valid time zone and an increasing period of up to 366 days.",
        ) from None
    return ReportScope(
        from_at=start.astimezone(UTC),
        to_at=end.astimezone(UTC),
        timezone=timezone,
        category=filters.category,
        team_id=filters.team_id,
        as_of=instant,
        generated_at=instant,
        today_partial=start.astimezone(UTC) <= instant < end.astimezone(UTC),
    )


def parameters(uow: UnitOfWork, scope: ReportScope) -> dict[str, Any]:
    return {
        "workspace": uow.scope.workspace_id,
        "from_at": scope.from_at,
        "to_at": scope.to_at,
        "as_of": scope.as_of,
        "category": scope.category,
        "team": scope.team_id,
        "timezone": scope.timezone,
    }


def rate(numerator: int, denominator: int) -> Rate:
    return Rate(
        numerator=numerator,
        denominator=denominator,
        share=numerator / denominator if denominator else None,
    )


def overview(uow: UnitOfWork, scope: ReportScope, bucket: Bucket) -> Overview:
    values = parameters(uow, scope)
    row = uow.session.execute(repository.METRICS, values).mappings().one()
    categories = [
        CategoryVolume.model_validate(item)
        for item in uow.session.execute(repository.CATEGORIES, values).mappings()
    ]
    return Overview(
        scope=scope,
        new_cases=row.new_cases,
        active_backlog=row.active_backlog,
        unassigned=row.unassigned,
        unanswered_overdue=row.unanswered_overdue,
        resolution_overdue=row.resolution_overdue,
        paused=row.paused,
        first_response=Durations(
            median_seconds=row.response_median,
            p90_seconds=row.response_p90,
            sample_count=row.response_count,
            attainment=rate(row.response_attained, row.response_count),
        ),
        resolution=Durations(
            median_seconds=row.resolution_median,
            p90_seconds=row.resolution_p90,
            sample_count=row.resolution_count,
            attainment=rate(row.resolution_attained, row.resolution_count),
        ),
        reopen=rate(row.reopen_numerator, row.reopen_eligible),
        immature_cycles=row.immature_cycles,
        csat=rate(row.favorable, row.rating_count),
        coverage=rate(row.rated, row.resolution_count),
        follow_up=rate(row.on_time, row.task_count),
        categories=categories,
        trend=trends(uow, scope, bucket),
    )


def trends(uow: UnitOfWork, scope: ReportScope, bucket: Bucket) -> Trends:
    values = {**parameters(uow, scope), "bucket": bucket}
    counts: dict[date, dict[str, int]] = {}
    keys: set[str] = set()
    for day, key, count in uow.session.execute(repository.TRENDS, values):
        counts.setdefault(day, {})[key] = count
        keys.add(key)
    zone = ZoneInfo(scope.timezone)
    start = scope.from_at.astimezone(zone).date()
    if bucket == "week":
        start -= timedelta(days=start.weekday())
    step = timedelta(days=1 if bucket == "day" else 7)
    points = []
    while datetime.combine(start, time.min, zone).astimezone(UTC) < scope.to_at:
        end = start + step
        categories = {key: counts.get(start, {}).get(key, 0) for key in sorted(keys)}
        points.append(
            TrendPoint(
                start=start,
                count=sum(categories.values()),
                categories=categories,
                partial=scope.today_partial and start <= scope.as_of.astimezone(zone).date() < end,
            )
        )
        start = end
    return Trends(scope=scope, bucket=bucket, points=points)


def records(
    uow: UnitOfWork,
    scope: ReportScope,
    filters: RecordFilters,
) -> tuple[list[MetricRecord], str | None]:
    binding = {
        "workspace": str(uow.scope.workspace_id),
        **filters.model_dump(mode="json", exclude={"cursor", "limit"}),
    }
    observed, identifier = None, None
    if filters.cursor:
        try:
            observed, identifier, observed_scope = read_cursor(filters.cursor, binding)
            # Current-state records use the report clock for display and ordering.
            # A cursor carries that clock so keyset paging remains stable.
            scope = scope.model_copy(update={"as_of": datetime.fromisoformat(observed_scope)})
        except ValueError:
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    statement = text(
        repository.COHORTS
        + ", records AS ("
        + repository.RECORDS[filters.metric]
        + """
        ) SELECT * FROM records
        WHERE CAST(:observed AS timestamptz) IS NULL OR (observed_at, id)
            < (CAST(:observed AS timestamptz), CAST(:identifier AS uuid))
        ORDER BY observed_at DESC, id DESC LIMIT :limit
    """
    )
    rows = [
        MetricRecord.model_validate(row)
        for row in uow.session.execute(
            statement,
            {
                **parameters(uow, scope),
                "observed": observed,
                "identifier": identifier,
                "limit": filters.limit + 1,
            },
        ).mappings()
    ]
    cursor = None
    if len(rows) > filters.limit:
        last = rows[filters.limit - 1]
        cursor = sign_cursor(
            binding,
            [
                last.observed_at.isoformat(),
                str(last.id),
                scope.as_of.isoformat(),
            ],
        )
    return rows[: filters.limit], cursor


def csv_cell(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, str) and (
        value.startswith(("\t", "\r")) or value.lstrip().startswith(("=", "+", "-", "@"))
    ):
        return "'" + value
    return value


EXPORT_DEFINITIONS = {
    "cases": "Cases created in the selected period. Category and team reflect current assignment.",
    "tasks": "Non-cancelled tasks due through as-of. On time means completed by due_at.",
    "feedback": "Ratings submitted in the selected period. Ratings 4 and 5 are favorable.",
}


def export(uow: UnitOfWork, scope: ReportScope, filters: ExportFilters, request_id: str) -> str:
    require_role(uow.scope, "admin", "manager")
    statement = text(repository.COHORTS + repository.EXPORTS[filters.report] + " LIMIT 10001")
    result = uow.session.execute(statement, parameters(uow, scope))
    rows = result.all()
    if len(rows) > 10000:
        raise Fault(413, "report_too_large", "Narrow the report to at most 10,000 records.")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "report",
            "generated_at_utc",
            "as_of_utc",
            "from_utc",
            "to_utc_exclusive",
            "timezone",
            "current_category",
            "current_team",
            "definition",
        ]
    )
    writer.writerow(
        [
            csv_cell(value)
            for value in (
                filters.report,
                scope.generated_at,
                scope.as_of,
                scope.from_at,
                scope.to_at,
                scope.timezone,
                scope.category,
                scope.team_id,
                EXPORT_DEFINITIONS[filters.report],
            )
        ]
    )
    writer.writerow(result.keys())
    writer.writerows([csv_cell(value) for value in row] for row in rows)
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "analytics.exported",
        "analytics_report",
        None,
        ["report", "filters", "row_count"],
        request_id,
        reason=f"{filters.report}; {len(rows)} rows; {scope.from_at.isoformat()} "
        f"through {scope.to_at.isoformat()}; {scope.timezone}; "
        f"category={scope.category}; team={scope.team_id}",
    )
    return output.getvalue()
