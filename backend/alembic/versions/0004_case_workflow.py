# ruff: noqa: E501
"""M2 cases, immutable conversations, scoped replay metadata, and published defaults."""

import sqlalchemy as sa

from alembic import op

revision = "0004_case_workflow"
down_revision = "0003_setup_acceptance"
branch_labels = None
depends_on = None

TABLES = [
    "case_config_versions",
    "workspace_counters",
    "cases",
    "case_cycles",
    "messages",
    "case_read_markers",
    "case_transitions",
    "idempotency_records",
]
DDL = [
    """CREATE TABLE case_config_versions (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	number INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	definition_json JSONB NOT NULL, 
	created_by_member_id UUID NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (workspace_id, number), 
	FOREIGN KEY(workspace_id, created_by_member_id) REFERENCES memberships (workspace_id, id), 
	CHECK (status IN ('draft','published')), 
	CHECK (number > 0 AND version > 0), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE TABLE workspace_counters (
	workspace_id UUID NOT NULL, 
	next_case_number BIGINT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (workspace_id), 
	CHECK (next_case_number > 0), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE TABLE cases (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	number BIGINT NOT NULL, 
	customer_id UUID NOT NULL, 
	requester_contact_id UUID NOT NULL, 
	config_version_id UUID NOT NULL, 
	category_key VARCHAR(50) NOT NULL, 
	subject VARCHAR(200) NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	priority VARCHAR(10) NOT NULL, 
	team_id UUID, 
	assignee_member_id UUID, 
	custom_values JSONB NOT NULL, 
	related_case_id UUID, 
	first_response_at TIMESTAMP WITH TIME ZONE, 
	first_response_target_seconds INTEGER NOT NULL, 
	resolution_target_seconds INTEGER NOT NULL, 
	last_public_message_seq BIGINT, 
	last_message_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	current_cycle_number INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (workspace_id, number), 
	FOREIGN KEY(workspace_id, customer_id, requester_contact_id) REFERENCES contacts (workspace_id, customer_id, id), 
	FOREIGN KEY(workspace_id, customer_id) REFERENCES customers (workspace_id, id), 
	FOREIGN KEY(workspace_id, config_version_id) REFERENCES case_config_versions (workspace_id, id), 
	FOREIGN KEY(workspace_id, team_id) REFERENCES teams (workspace_id, id), 
	FOREIGN KEY(workspace_id, assignee_member_id) REFERENCES memberships (workspace_id, id), 
	FOREIGN KEY(workspace_id, related_case_id) REFERENCES cases (workspace_id, id), 
	CHECK (state IN ('new','open','pending_customer','resolved','closed')), 
	CHECK (priority IN ('urgent','high','normal','low')), 
	CHECK (source IN ('portal','manual_phone','manual_email','manual_other')), 
	CHECK (version > 0 AND number > 0 AND current_cycle_number > 0), 
	CHECK (first_response_target_seconds > 0 AND resolution_target_seconds > 0), 
	CHECK (state = 'new' OR assignee_member_id IS NOT NULL), 
	CHECK (related_case_id IS NULL OR related_case_id != id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_cases_assignee ON cases (workspace_id, assignee_member_id, state)""",
    """CREATE INDEX ix_cases_customer ON cases (workspace_id, customer_id, created_at, id)""",
    """CREATE INDEX ix_cases_last_message ON cases (workspace_id, last_message_at, id)""",
    """CREATE INDEX ix_cases_queue ON cases (workspace_id, state, priority, created_at, id)""",
    """CREATE TABLE case_cycles (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	case_id UUID NOT NULL, 
	cycle_number INTEGER NOT NULL, 
	opened_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	target_seconds INTEGER NOT NULL, 
	paused_seconds FLOAT NOT NULL, 
	pause_started_at TIMESTAMP WITH TIME ZONE, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	resolved_by_member_id UUID, 
	resolution_code VARCHAR(20), 
	resolution_summary VARCHAR(4000), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (workspace_id, case_id, cycle_number), 
	FOREIGN KEY(workspace_id, case_id) REFERENCES cases (workspace_id, id), 
	FOREIGN KEY(workspace_id, resolved_by_member_id) REFERENCES memberships (workspace_id, id), 
	CHECK (cycle_number > 0 AND target_seconds > 0 AND paused_seconds >= 0), 
	CHECK (resolved_at IS NULL OR resolved_at >= opened_at), 
	CHECK (pause_started_at IS NULL OR pause_started_at >= opened_at), 
	CHECK (resolved_at IS NULL OR (pause_started_at IS NULL AND resolved_by_member_id IS NOT NULL AND resolution_code IS NOT NULL AND length(btrim(resolution_summary)) > 0)), 
	CHECK (resolution_code IS NULL OR resolution_code IN ('answered','fixed','fulfilled','declined','duplicate','other')), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_case_cycle_resolution ON case_cycles (workspace_id, resolved_at)""",
    """CREATE UNIQUE INDEX uq_case_unfinished_cycle ON case_cycles (workspace_id, case_id) WHERE resolved_at IS NULL""",
    """CREATE TABLE messages (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	case_id UUID NOT NULL, 
	sequence BIGINT GENERATED BY DEFAULT AS IDENTITY, 
	author_user_id UUID, 
	author_kind VARCHAR(10) NOT NULL, 
	visibility VARCHAR(10) NOT NULL, 
	message_kind VARCHAR(20) NOT NULL, 
	body TEXT NOT NULL, 
	updated_case_version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (case_id, sequence), 
	UNIQUE (workspace_id, case_id, id), 
	FOREIGN KEY(workspace_id, case_id) REFERENCES cases (workspace_id, id), 
	CHECK (author_kind IN ('staff','contact','system')), 
	CHECK (visibility IN ('public','internal')), 
	CHECK (message_kind IN ('initial','reply','note','resolution','info_request','reopen')), 
	CHECK (length(btrim(body)) BETWEEN 1 AND 10000), 
	CHECK ((visibility = 'internal' AND message_kind = 'note' AND author_kind = 'staff') OR (visibility = 'public' AND message_kind != 'note')), 
	CHECK (updated_case_version > 0), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	UNIQUE (sequence), 
	FOREIGN KEY(author_user_id) REFERENCES users (id)
)""",
    """CREATE INDEX ix_messages_conversation ON messages (workspace_id, case_id, sequence)""",
    """CREATE TABLE case_read_markers (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	case_id UUID NOT NULL, 
	member_id UUID NOT NULL, 
	last_read_sequence BIGINT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, case_id, member_id), 
	FOREIGN KEY(workspace_id, case_id) REFERENCES cases (workspace_id, id), 
	FOREIGN KEY(workspace_id, member_id) REFERENCES memberships (workspace_id, id), 
	CHECK (last_read_sequence >= 0), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE TABLE case_transitions (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	case_id UUID NOT NULL, 
	cycle_number INTEGER NOT NULL, 
	from_state VARCHAR(20), 
	to_state VARCHAR(20) NOT NULL, 
	actor_user_id UUID, 
	reason VARCHAR(4000), 
	message_id UUID, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	FOREIGN KEY(workspace_id, case_id, cycle_number) REFERENCES case_cycles (workspace_id, case_id, cycle_number), 
	FOREIGN KEY(workspace_id, case_id, message_id) REFERENCES messages (workspace_id, case_id, id), 
	CHECK (to_state IN ('new','open','pending_customer','resolved','closed')), 
	CHECK (from_state IS NULL OR from_state IN ('new','open','pending_customer','resolved','closed')), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id)
)""",
    """CREATE INDEX ix_case_transition_time ON case_transitions (workspace_id, case_id, occurred_at, id)""",
    """CREATE TABLE idempotency_records (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	principal_key VARCHAR(100) NOT NULL, 
	route_key VARCHAR(200) NOT NULL, 
	key VARCHAR(128) NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	resource_type VARCHAR(20), 
	resource_id UUID, 
	response_status INTEGER NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, principal_key, route_key, key), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
]
DEFAULT_DEFINITION = '{"categories":[{"key":"access","label":"Access","default_team_id":null},{"key":"billing_question","label":"Billing question","default_team_id":null},{"key":"product_issue","label":"Product issue","default_team_id":null}],"state_labels":{"new":"New","open":"Open","pending_customer":"Awaiting customer","resolved":"Resolved","closed":"Closed"},"priorities":{"urgent":{"response_minutes":60,"resolution_minutes":480},"high":{"response_minutes":240,"resolution_minutes":1440},"normal":{"response_minutes":480,"resolution_minutes":2880},"low":{"response_minutes":1440,"resolution_minutes":5760}},"fields":[],"portal_default_priority":"normal"}'


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("active_case_config_id", sa.Uuid()))
    for statement in DDL:
        op.execute(statement)
    op.create_foreign_key(
        "fk_workspace_case_config",
        "workspaces",
        "case_config_versions",
        ["id", "active_case_config_id"],
        ["workspace_id", "id"],
    )
    scope = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    staff = "current_setting('app.audience', true) = 'staff'"
    own_case = "requester_contact_id = NULLIF(current_setting('app.contact_id', true), '')::uuid"
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        reader = staff
        writer = staff
        if table == "cases":
            reader = (
                f"({staff} OR (current_setting('app.audience', true) = 'portal' AND {own_case}))"
            )
        elif table == "messages":
            reader = f"({staff} OR (current_setting('app.audience', true) = 'portal' AND visibility = 'public' AND EXISTS (SELECT 1 FROM cases c WHERE c.workspace_id = messages.workspace_id AND c.id = messages.case_id AND c.{own_case})))"
        elif table == "case_read_markers":
            own_marker = "(current_user = 'atlas_migrator' OR member_id IN (SELECT id FROM memberships WHERE user_id = NULLIF(current_setting('app.user_id', true), '')::uuid))"
            reader = writer = f"({staff} AND {own_marker})"
        op.execute(f"CREATE POLICY m2_read ON {table} FOR SELECT USING ({scope} AND ({reader}))")
        op.execute(
            f"CREATE POLICY m2_insert ON {table} FOR INSERT WITH CHECK ({scope} AND ({writer}))"
        )
        op.execute(
            f"CREATE POLICY m2_operator_cleanup ON {table} FOR DELETE TO atlas_migrator USING ({scope})"
        )
        if table not in {"messages", "case_transitions"}:
            op.execute(
                f"CREATE POLICY m2_update ON {table} FOR UPDATE USING ({scope} AND ({writer})) WITH CHECK ({scope} AND ({writer}))"
            )
        grants = (
            "SELECT, INSERT"
            if table in {"messages", "case_transitions"}
            else "SELECT, INSERT, UPDATE"
        )
        op.execute(f"GRANT {grants} ON {table} TO atlas_app")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE messages_sequence_seq TO atlas_app")
    op.execute("""CREATE FUNCTION atlas_published_config_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.status = 'published' THEN
            RAISE EXCEPTION 'Published case configurations are immutable' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END; $$""")
    op.execute(
        "CREATE TRIGGER immutable_published_config BEFORE UPDATE ON case_config_versions FOR EACH ROW EXECUTE FUNCTION atlas_published_config_immutable()"
    )
    # FORCE RLS applies to the migration owner. These policies exist only inside
    # this migration transaction and never grant broader access to atlas_app.
    for table in ("workspaces", "memberships", "case_config_versions", "workspace_counters"):
        op.execute(
            f"CREATE POLICY m2_seed ON {table} TO atlas_migrator USING (true) WITH CHECK (true)"
        )
    connection = op.get_bind()
    connection.execute(
        sa.text("""
        INSERT INTO case_config_versions
          (id, workspace_id, number, version, status, definition_json, created_by_member_id, published_at)
        SELECT gen_random_uuid(), w.id, 1, 1, 'published', CAST(:definition AS jsonb), m.id, now()
        FROM workspaces w JOIN LATERAL
          (SELECT id FROM memberships WHERE workspace_id=w.id AND active AND role='admin'
           ORDER BY created_at, id LIMIT 1) m ON true
        WHERE w.active_case_config_id IS NULL
    """),
        {"definition": DEFAULT_DEFINITION},
    )
    op.execute("""UPDATE workspaces w SET active_case_config_id = c.id
                  FROM case_config_versions c WHERE c.workspace_id=w.id AND c.number=1
                  AND w.active_case_config_id IS NULL""")
    op.execute(
        "INSERT INTO workspace_counters(workspace_id,next_case_number) SELECT id,1 FROM workspaces"
    )
    for table in ("workspaces", "memberships", "case_config_versions", "workspace_counters"):
        op.execute(f"DROP POLICY m2_seed ON {table}")


def downgrade() -> None:
    op.drop_constraint("fk_workspace_case_config", "workspaces", type_="foreignkey")
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP FUNCTION atlas_published_config_immutable()")
    op.drop_column("workspaces", "active_case_config_id")
