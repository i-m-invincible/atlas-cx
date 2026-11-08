# ruff: noqa: E501
"""M1 identity, customer core, composite constraints and forced RLS."""

import sqlalchemy as sa

from alembic import op

revision = "0002_identity_customers"
down_revision = "0001_workspace_boundary"
branch_labels = None
depends_on = None

TABLES = [
    "users",
    "memberships",
    "customers",
    "contacts",
    "portal_bindings",
    "sessions",
    "setup_tokens",
    "auth_rate_limits",
    "teams",
    "team_members",
    "audit_events",
]
TENANT_TABLES = [
    "memberships",
    "customers",
    "contacts",
    "portal_bindings",
    "teams",
    "team_members",
    "audit_events",
]


DDL = [
    """CREATE TABLE users (
	id UUID NOT NULL, 
	normalized_email VARCHAR(254) NOT NULL, 
	display_name VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(512), 
	disabled_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (normalized_email)
)
    """,
    """CREATE TABLE memberships (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	invited_display_name VARCHAR(120),
	active BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (workspace_id, user_id), 
	CHECK (role IN ('admin','manager','agent','viewer')), 
	CHECK (version > 0), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)
    """,
    """CREATE TABLE customers (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	lifecycle VARCHAR(16) NOT NULL, 
	external_id VARCHAR(120), 
	owner_member_id UUID, 
	tags VARCHAR(40)[] NOT NULL, 
	activity_expected BOOLEAN NOT NULL, 
	tracking_started_at TIMESTAMP WITH TIME ZONE, 
	archived_at TIMESTAMP WITH TIME ZONE, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (workspace_id, external_id), 
	FOREIGN KEY(workspace_id, owner_member_id) REFERENCES memberships (workspace_id, id), 
	CHECK (kind IN ('person','business')), 
	CHECK (lifecycle IN ('prospect','active','inactive')), 
	CHECK (version > 0), 
	CHECK (cardinality(tags) <= 20), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)
    """,
    """CREATE INDEX ix_customers_workspace_id ON customers (workspace_id)
    """,
    """CREATE TABLE contacts (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	customer_id UUID NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	normalized_email VARCHAR(254) NOT NULL, 
	phone VARCHAR(32), 
	archived_at TIMESTAMP WITH TIME ZONE, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (workspace_id, customer_id, id), 
	UNIQUE (workspace_id, normalized_email), 
	FOREIGN KEY(workspace_id, customer_id) REFERENCES customers (workspace_id, id), 
	CHECK (version > 0), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)
    """,
    """CREATE TABLE portal_bindings (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	contact_id UUID NOT NULL, 
	active BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (workspace_id, user_id), 
	UNIQUE (workspace_id, contact_id), 
	FOREIGN KEY(workspace_id, contact_id) REFERENCES contacts (workspace_id, id), 
	CHECK (version > 0), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)
    """,
    """CREATE TABLE sessions (
	id UUID NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	csrf_secret_hash VARCHAR(64) NOT NULL, 
	user_id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	audience VARCHAR(8) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	absolute_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CHECK (audience IN ('staff','portal')), 
	UNIQUE (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)
    """,
    """CREATE TABLE setup_tokens (
	id UUID NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	workspace_id UUID, 
	user_id UUID NOT NULL, 
	membership_id UUID, 
	portal_binding_id UUID, 
	purpose VARCHAR(16) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id, membership_id) REFERENCES memberships (workspace_id, id), 
	FOREIGN KEY(workspace_id, portal_binding_id) REFERENCES portal_bindings (workspace_id, id), 
	CHECK ((purpose = 'staff_setup' AND workspace_id IS NOT NULL AND membership_id IS NOT NULL AND portal_binding_id IS NULL) OR (purpose = 'portal_setup' AND workspace_id IS NOT NULL AND membership_id IS NULL AND portal_binding_id IS NOT NULL) OR (purpose = 'recovery' AND workspace_id IS NULL AND membership_id IS NULL AND portal_binding_id IS NULL)), 
	UNIQUE (token_hash), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)
    """,
    """CREATE TABLE auth_rate_limits (
	principal_key VARCHAR(80) NOT NULL, 
	window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	failures INTEGER NOT NULL, 
	PRIMARY KEY (principal_key, window_start)
)
    """,
    """CREATE TABLE teams (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	archived_at TIMESTAMP WITH TIME ZONE, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	CHECK (version > 0), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)
    """,
    """CREATE TABLE team_members (
	workspace_id UUID NOT NULL, 
	team_id UUID NOT NULL, 
	member_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (workspace_id, team_id, member_id), 
	FOREIGN KEY(workspace_id, team_id) REFERENCES teams (workspace_id, id), 
	FOREIGN KEY(workspace_id, member_id) REFERENCES memberships (workspace_id, id)
)
    """,
    """CREATE TABLE audit_events (
	id UUID NOT NULL, 
	sequence BIGINT GENERATED BY DEFAULT AS IDENTITY, 
	workspace_id UUID NOT NULL, 
	actor_user_id UUID, 
	actor_kind VARCHAR(16) NOT NULL, 
	action VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(40) NOT NULL, 
	entity_id UUID, 
	changed_fields JSONB NOT NULL, 
	reason VARCHAR(2000), 
	request_id VARCHAR(64) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, id), 
	UNIQUE (sequence), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id)
)
    """,
]


def upgrade() -> None:
    # Frozen DDL keeps this migration independent of future ORM changes.
    for statement in DDL:
        op.execute(statement)
    op.add_column("workspaces", sa.Column("feedback_manager_member_id", sa.Uuid(), nullable=True))
    op.add_column("workspaces", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "workspaces", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default="false")
    )
    op.create_foreign_key(
        "fk_workspace_feedback_manager",
        "workspaces",
        "memberships",
        ["id", "feedback_manager_member_id"],
        ["workspace_id", "id"],
    )
    scope = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    staff = "COALESCE(current_setting('app.audience', true), 'staff') = 'staff'"
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        predicate = f"({scope}) AND ({staff})"
        read_predicate = predicate
        if table == "contacts":
            read_predicate = (
                f"({scope}) AND (({staff}) OR (id = "
                "NULLIF(current_setting('app.contact_id', true), '')::uuid))"
            )
        elif table == "portal_bindings":
            read_predicate = (
                f"({scope}) AND (({staff}) OR (user_id = "
                "NULLIF(current_setting('app.user_id', true), '')::uuid))"
            )
        op.execute(f"CREATE POLICY tenant_read ON {table} FOR SELECT USING ({read_predicate})")
        for operation in ("INSERT", "UPDATE", "DELETE"):
            clause = (
                f"WITH CHECK ({predicate})" if operation == "INSERT" else f"USING ({predicate})"
            )
            if operation == "UPDATE":
                clause += f" WITH CHECK ({predicate})"
            op.execute(
                f"CREATE POLICY tenant_{operation.lower()} ON {table} FOR {operation} {clause}"
            )
        permissions = "SELECT, INSERT" if table == "audit_events" else "SELECT, INSERT, UPDATE"
        if table == "team_members":
            permissions += ", DELETE"
        op.execute(f"GRANT {permissions} ON {table} TO atlas_app")
    for table in ("users", "sessions", "setup_tokens", "auth_rate_limits"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO atlas_app")
    op.execute("GRANT USAGE ON SEQUENCE audit_events_sequence_seq TO atlas_app")
    # Only the authentication repository sets this short-lived exact-slug context.
    op.execute(
        "CREATE POLICY login_workspace_lookup ON workspaces FOR SELECT "
        "USING (slug = current_setting('app.login_workspace', true))"
    )
    op.create_index("uq_team_name", "teams", ["workspace_id", sa.text("lower(name)")], unique=True)
    op.create_index("ix_customer_page", "customers", ["workspace_id", "created_at", "id"])
    op.create_index("ix_customer_name", "customers", ["workspace_id", "name", "id"])
    op.create_index(
        "ix_contact_customer", "contacts", ["workspace_id", "customer_id", "created_at", "id"]
    )


def downgrade() -> None:
    op.execute("DROP POLICY login_workspace_lookup ON workspaces")
    op.drop_constraint("fk_workspace_feedback_manager", "workspaces", type_="foreignkey")
    for column in ("feedback_manager_member_id", "archived_at", "is_demo"):
        op.drop_column("workspaces", column)
    for table in reversed(TABLES):
        op.drop_table(table)
