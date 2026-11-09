"""Scoped SQL projections over recorded service observations."""

from sqlalchemy import text

# Bind values once. Team and category always refer to the case's assignment in
# this snapshot, including when a response, resolution or rating is historical.
COHORTS = """
    WITH bounds AS (
        SELECT CAST(:workspace AS uuid) AS workspace, CAST(:from_at AS timestamptz) AS start_at,
            CAST(:to_at AS timestamptz) AS end_at, CAST(:as_of AS timestamptz) AS observed_at,
            CAST(:category AS text) AS category, CAST(:team AS uuid) AS team
    ), scoped_cases AS NOT MATERIALIZED (
        SELECT c.* FROM cases c CROSS JOIN bounds b
        WHERE c.workspace_id = b.workspace AND c.created_at <= b.observed_at
            AND (b.category IS NULL OR c.category_key = b.category)
            AND (b.team IS NULL OR c.team_id = b.team)
    ), period_cases AS NOT MATERIALIZED (
        SELECT c.* FROM scoped_cases c CROSS JOIN bounds b
        WHERE c.created_at >= b.start_at AND c.created_at < b.end_at
    ), responses AS (
        SELECT c.*, extract(epoch FROM c.first_response_at - c.created_at)::float8 AS seconds
        FROM scoped_cases c CROSS JOIN bounds b
        WHERE c.first_response_at >= b.start_at AND c.first_response_at < b.end_at
            AND c.first_response_at <= b.observed_at
    ), resolved AS (
        SELECT y.*, c.subject, c.number,
            extract(epoch FROM y.resolved_at - y.opened_at)::float8 - y.paused_seconds AS seconds,
            y.resolved_at <= b.observed_at - interval '168 hours' AS mature,
            EXISTS (
                SELECT 1 FROM case_cycles n
                WHERE (n.workspace_id, n.case_id, n.cycle_number)
                    = (y.workspace_id, y.case_id, y.cycle_number + 1)
                    AND n.opened_at >= y.resolved_at
                    AND n.opened_at <= y.resolved_at + interval '168 hours'
                    AND n.opened_at <= b.observed_at
            ) AS reopened,
            f.id IS NOT NULL AS rated
        FROM scoped_cases c JOIN case_cycles y
            ON (y.workspace_id, y.case_id) = (c.workspace_id, c.id)
        CROSS JOIN bounds b
        LEFT JOIN feedback f ON (f.workspace_id, f.case_id, f.cycle_number)
            = (y.workspace_id, y.case_id, y.cycle_number) AND f.created_at <= b.observed_at
        WHERE y.resolved_at >= b.start_at AND y.resolved_at < b.end_at
            AND y.resolved_at <= b.observed_at
    ), ratings AS (
        SELECT f.*, c.number, c.subject FROM scoped_cases c
        JOIN feedback f ON (f.workspace_id, f.case_id) = (c.workspace_id, c.id)
        CROSS JOIN bounds b
        WHERE f.created_at >= b.start_at AND f.created_at < b.end_at
            AND f.created_at <= b.observed_at
    ), due_tasks AS (
        SELECT t.*, coalesce(t.completed_at <= t.due_at, false) AS completed_on_time
        FROM tasks t CROSS JOIN bounds b
        WHERE t.workspace_id = b.workspace AND t.created_at <= b.observed_at
            AND t.due_at >= b.start_at AND t.due_at < b.end_at AND t.due_at <= b.observed_at
            AND t.state <> 'cancelled'
            AND ((b.category IS NULL AND b.team IS NULL) OR EXISTS (
                SELECT 1 FROM scoped_cases c
                WHERE c.id = t.case_id AND c.workspace_id = t.workspace_id
            ))
    ), current_work AS (
        SELECT c.*, b.observed_at,
            c.state = 'new' AND c.assignee_member_id IS NULL AS is_unassigned,
            c.first_response_at IS NULL
                AND extract(epoch FROM b.observed_at - c.created_at)
                    > c.first_response_target_seconds AS response_overdue,
            y.pause_started_at IS NOT NULL AS paused,
            coalesce(extract(epoch FROM b.observed_at - y.opened_at) - y.paused_seconds
                - coalesce(extract(epoch FROM b.observed_at - y.pause_started_at), 0)
                    > y.target_seconds, false) AS resolution_overdue
        FROM scoped_cases c CROSS JOIN bounds b
        LEFT JOIN case_cycles y ON (y.workspace_id, y.case_id, y.cycle_number)
            = (c.workspace_id, c.id, c.current_cycle_number)
            AND y.opened_at <= b.observed_at AND y.resolved_at IS NULL
        WHERE c.state IN ('new', 'open', 'pending_customer')
    )
"""

METRICS = text(
    COHORTS
    + """
    SELECT * FROM
        (SELECT count(*) AS new_cases FROM period_cases) volume,
        (SELECT count(*) AS active_backlog, count(*) FILTER (WHERE is_unassigned) AS unassigned,
            count(*) FILTER (WHERE response_overdue) AS unanswered_overdue,
            count(*) FILTER (WHERE resolution_overdue) AS resolution_overdue,
            count(*) FILTER (WHERE paused) AS paused FROM current_work) current_counts,
        (SELECT count(*) AS response_count,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds) AS response_median,
            percentile_cont(0.9) WITHIN GROUP (ORDER BY seconds) AS response_p90,
            count(*) FILTER (WHERE seconds <= first_response_target_seconds) AS response_attained
            FROM responses) response_stats,
        (SELECT count(*) AS resolution_count,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds) AS resolution_median,
            percentile_cont(0.9) WITHIN GROUP (ORDER BY seconds) AS resolution_p90,
            count(*) FILTER (WHERE seconds <= target_seconds) AS resolution_attained,
            count(*) FILTER (WHERE mature) AS reopen_eligible,
            count(*) FILTER (WHERE mature AND reopened) AS reopen_numerator,
            count(*) FILTER (WHERE NOT mature) AS immature_cycles,
            count(*) FILTER (WHERE rated) AS rated FROM resolved) resolution_stats,
        (SELECT count(*) AS rating_count, count(*) FILTER (WHERE rating >= 4) AS favorable
            FROM ratings) rating_stats,
        (SELECT count(*) AS task_count, count(*) FILTER (WHERE completed_on_time) AS on_time
            FROM due_tasks) task_stats
"""
)

CATEGORIES = text(
    COHORTS
    + """
    SELECT c.category_key AS key, count(*) AS count,
        (array_agg(coalesce(cat.value->>'label', c.category_key)
            ORDER BY cfg.number DESC, c.created_at DESC, c.id DESC))[1] AS label
    FROM period_cases c JOIN case_config_versions cfg
        ON (cfg.workspace_id, cfg.id) = (c.workspace_id, c.config_version_id)
    LEFT JOIN LATERAL jsonb_array_elements(cfg.definition_json->'categories') cat(value)
        ON cat.value->>'key' = c.category_key
    GROUP BY c.category_key ORDER BY count DESC, key
"""
)

TRENDS = text(
    COHORTS
    + """
    SELECT CAST(date_trunc(:bucket, timezone(:timezone, created_at)) AS date) AS start,
        category_key, count(*) AS count FROM period_cases
    GROUP BY start, category_key ORDER BY start
"""
)

# These constant projections reuse the same cohorts as the aggregate measures.
# No request values are interpolated into SQL.
CASE_RECORD = """
    SELECT id, 'case' AS record_type, id AS reference_id,
        concat('#', number, ' · ', subject) AS title,
        {observed} AS observed_at, true AS eligible, {meets} AS meets_measure, {seconds} AS seconds,
        CAST(NULL AS integer) AS cycle_number FROM {cohort} {predicate}
"""
CYCLE_RECORD = """
    SELECT id, 'case' AS record_type, case_id AS reference_id,
        concat('#', number, ' · ', subject) AS title, resolved_at AS observed_at,
        {eligible} AS eligible, {meets} AS meets_measure, seconds, cycle_number FROM resolved
"""
RECORDS = {
    "new_cases": CASE_RECORD.format(
        observed="created_at",
        meets="CAST(NULL AS boolean)",
        seconds="CAST(NULL AS float8)",
        cohort="period_cases",
        predicate="",
    ),
    "first_response": CASE_RECORD.format(
        observed="first_response_at",
        meets="seconds <= first_response_target_seconds",
        seconds="seconds",
        cohort="responses",
        predicate="",
    ),
    "resolution": CYCLE_RECORD.format(eligible="true", meets="seconds <= target_seconds"),
    "reopen": CYCLE_RECORD.format(eligible="mature", meets="CASE WHEN mature THEN reopened END"),
    "coverage": CYCLE_RECORD.format(eligible="true", meets="rated"),
    "csat": """
        SELECT id, 'feedback' AS record_type, case_id AS reference_id,
            concat('#', number, ' · ', rating, ' / 5') AS title, created_at AS observed_at,
            true AS eligible, rating >= 4 AS meets_measure, CAST(NULL AS float8) AS seconds,
            cycle_number FROM ratings
    """,
    "follow_up": """
        SELECT id, 'task' AS record_type, id AS reference_id, title, due_at AS observed_at,
            true AS eligible, completed_on_time AS meets_measure, CAST(NULL AS float8) AS seconds,
            CAST(NULL AS integer) AS cycle_number FROM due_tasks
    """,
}
RECORDS.update(
    {
        name: CASE_RECORD.format(
            observed="observed_at",
            meets="CAST(NULL AS boolean)",
            seconds="CAST(NULL AS float8)",
            cohort="current_work",
            predicate=predicate,
        )
        for name, predicate in {
            "backlog": "",
            "unassigned": "WHERE is_unassigned",
            "response_overdue": "WHERE response_overdue",
            "resolution_overdue": "WHERE resolution_overdue",
            "paused": "WHERE paused",
        }.items()
    }
)

EXPORTS = {
    "cases": """
        SELECT id, number, customer_id, subject, category_key, team_id, state, created_at,
            first_response_at, first_response_target_seconds, resolution_target_seconds
        FROM period_cases ORDER BY created_at DESC, id DESC
    """,
    "tasks": """
        SELECT id, case_id, customer_id, title, state, due_at, completed_at, completed_on_time
        FROM due_tasks ORDER BY due_at DESC, id DESC
    """,
    "feedback": """
        SELECT id, case_id, cycle_number, rating, created_at FROM ratings
        ORDER BY created_at DESC, id DESC
    """,
}
