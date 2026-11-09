# ruff: noqa: E501
"""M4 recorded activity, ingestion credentials, and reporting indexes."""

from alembic import op

revision = "0006_activity_analytics"
down_revision = "0005_followups_imports"
branch_labels = None
depends_on = None

DDL = [
    """CREATE TABLE event_definitions (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    key VARCHAR(50) NOT NULL,
    label VARCHAR(120) NOT NULL,
    allowed_properties_json JSONB NOT NULL,
    counts_as_activity BOOLEAN NOT NULL,
    enabled BOOLEAN NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, key),
    CHECK (version > 0 AND jsonb_typeof(allowed_properties_json) = 'object'),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE TABLE customer_events (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    event_definition_id UUID NOT NULL,
    external_event_id VARCHAR(120) NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL,
    safe_properties JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    activity_flag_snapshot BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, external_event_id),
    FOREIGN KEY(workspace_id, customer_id) REFERENCES customers (workspace_id, id),
    FOREIGN KEY(workspace_id, event_definition_id) REFERENCES event_definitions (workspace_id, id),
    CHECK (jsonb_typeof(safe_properties) = 'object'),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_customer_events_retention ON customer_events (workspace_id, received_at)""",
    """CREATE INDEX ix_customer_events_timeline ON customer_events (workspace_id, customer_id, occurred_at, id)""",
    """CREATE TABLE api_credentials (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    name VARCHAR(120) NOT NULL,
    token_prefix VARCHAR(24) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    scope VARCHAR(20) NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    version INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    CHECK (scope = 'events:write' AND version > 0),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
    UNIQUE (token_hash)
)""",
    """CREATE TABLE rate_limit_buckets (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    principal_key VARCHAR(100) NOT NULL,
    operation VARCHAR(50) NOT NULL,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    request_count INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, principal_key, operation, window_start),
    CHECK (request_count > 0),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
]

INDEXES = (
    ("ix_cases_report_created", "cases", ["workspace_id", "created_at", "id"]),
    ("ix_cases_report_response", "cases", ["workspace_id", "first_response_at", "id"]),
    ("ix_feedback_report_created", "feedback", ["workspace_id", "created_at", "id"]),
    ("ix_tasks_report_due", "tasks", ["workspace_id", "due_at", "id"]),
)


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)
    scope = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    staff = "current_setting('app.audience', true) = 'staff'"
    credential = "NULLIF(current_setting('app.ingest_credential', true), '')"
    ingest = f"(current_setting('app.audience', true) = 'ingest' AND {credential} IS NOT NULL)"
    own = f"({ingest} AND id = {credential}::uuid)"
    rate = f"({ingest} AND principal_key = {credential} AND operation = 'events.batch')"
    digest = "token_hash = NULLIF(current_setting('app.credential_hash', true), '')"
    policies = {
        "event_definitions": (f"{staff} OR {ingest}", staff, staff, None),
        "customer_events": (f"{staff} OR {ingest}", ingest, None, None),
        "api_credentials": (f"{staff} OR {own}", staff, f"{staff} OR {own}", None),
        "rate_limit_buckets": (f"{staff} OR {rate}", rate, rate, rate),
    }
    for table, (read, insert, update, delete) in policies.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        select = f"{scope} AND ({read})"
        if table == "api_credentials":
            select = f"({digest}) OR ({select})"
        op.execute(f"CREATE POLICY m4_read ON {table} FOR SELECT USING ({select})")
        op.execute(
            f"CREATE POLICY m4_insert ON {table} FOR INSERT WITH CHECK ({scope} AND ({insert}))"
        )
        grants = ["SELECT", "INSERT"]
        if update:
            predicate = f"{scope} AND ({update})"
            op.execute(
                f"CREATE POLICY m4_update ON {table} FOR UPDATE USING ({predicate}) WITH CHECK ({predicate})"
            )
            grants.append("UPDATE")
        if delete:
            op.execute(
                f"CREATE POLICY m4_delete ON {table} FOR DELETE USING ({scope} AND ({delete}))"
            )
            grants.append("DELETE")
        op.execute(
            f"CREATE POLICY m4_operator_cleanup ON {table} FOR DELETE TO atlas_migrator USING ({scope})"
        )
        op.execute(f"GRANT {', '.join(grants)} ON {table} TO atlas_app")
    op.execute(
        f"CREATE POLICY m4_customer_lookup ON customers FOR SELECT USING ({scope} AND {ingest})"
    )
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
    op.execute("DROP POLICY m4_customer_lookup ON customers")
    for table in ("rate_limit_buckets", "api_credentials", "customer_events", "event_definitions"):
        op.drop_table(table)
