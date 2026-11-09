# ruff: noqa: E501
"""M3 follow-up tasks, immutable resolution feedback, and staged CSV imports."""

from alembic import op

revision = "0005_followups_imports"
down_revision = "0004_case_workflow"
branch_labels = None
depends_on = None

DDL = [
    """CREATE TABLE feedback (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    case_id UUID NOT NULL,
    cycle_number INTEGER NOT NULL,
    requester_contact_id UUID NOT NULL,
    rating INTEGER NOT NULL,
    comment VARCHAR(2000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, case_id, id),
    UNIQUE (workspace_id, case_id, cycle_number),
    FOREIGN KEY(workspace_id, case_id, cycle_number) REFERENCES case_cycles (workspace_id, case_id, cycle_number),
    FOREIGN KEY(workspace_id, case_id, requester_contact_id) REFERENCES cases (workspace_id, id, requester_contact_id),
    CHECK (rating BETWEEN 1 AND 5),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE TABLE tasks (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    case_id UUID,
    feedback_id UUID,
    title VARCHAR(200) NOT NULL,
    description VARCHAR(4000),
    assignee_member_id UUID NOT NULL,
    due_at TIMESTAMP WITH TIME ZONE NOT NULL,
    state VARCHAR(16) NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    completed_by_member_id UUID,
    completion_note VARCHAR(2000),
    created_by_member_id UUID,
    version INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, feedback_id),
    FOREIGN KEY(workspace_id, customer_id) REFERENCES customers (workspace_id, id),
    FOREIGN KEY(workspace_id, customer_id, case_id) REFERENCES cases (workspace_id, customer_id, id),
    FOREIGN KEY(workspace_id, case_id, feedback_id) REFERENCES feedback (workspace_id, case_id, id),
    FOREIGN KEY(workspace_id, assignee_member_id) REFERENCES memberships (workspace_id, id),
    FOREIGN KEY(workspace_id, created_by_member_id) REFERENCES memberships (workspace_id, id),
    FOREIGN KEY(workspace_id, completed_by_member_id) REFERENCES memberships (workspace_id, id),
    CHECK (feedback_id IS NULL OR case_id IS NOT NULL),
    CHECK (state IN ('open','in_progress','completed','cancelled')),
    CHECK (version > 0 AND length(btrim(title)) > 0),
    CHECK ((state = 'completed' AND completed_at IS NOT NULL AND completed_by_member_id IS NOT NULL AND completion_note IS NOT NULL AND length(btrim(completion_note)) > 0) OR (state <> 'completed' AND completed_at IS NULL AND completed_by_member_id IS NULL AND completion_note IS NULL)),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_tasks_assignment ON tasks (workspace_id, assignee_member_id, state, due_at)""",
    """CREATE INDEX ix_tasks_customer ON tasks (workspace_id, customer_id, due_at, id)""",
    """CREATE TABLE customer_imports (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    submitted_by_member_id UUID NOT NULL,
    status VARCHAR(16) NOT NULL,
    input_hash VARCHAR(64) NOT NULL,
    normalized_rows_json JSONB NOT NULL,
    row_results_json JSONB NOT NULL,
    create_count INTEGER NOT NULL,
    update_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    version INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    FOREIGN KEY(workspace_id, submitted_by_member_id) REFERENCES memberships (workspace_id, id),
    CHECK (status IN ('validated','committed','failed','expired')),
    CHECK (version > 0 AND create_count >= 0 AND update_count >= 0 AND error_count >= 0),
    CHECK (jsonb_array_length(normalized_rows_json) <= 1000),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_customer_imports_expiry ON customer_imports (workspace_id, expires_at)""",
]


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_case_customer_reference", "cases", ["workspace_id", "customer_id", "id"]
    )
    op.create_unique_constraint(
        "uq_case_requester_reference", "cases", ["workspace_id", "id", "requester_contact_id"]
    )
    for statement in DDL:
        op.execute(statement)
    scope = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    staff = "current_setting('app.audience', true) = 'staff'"
    user = "NULLIF(current_setting('app.user_id', true), '')::uuid"
    contact = "NULLIF(current_setting('app.contact_id', true), '')::uuid"
    for table in ("feedback", "tasks", "customer_imports"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        read = write = staff
        if table == "feedback":
            read = f"""({staff} OR (
                current_setting('app.audience', true) = 'portal'
                AND requester_contact_id = {contact}
                AND EXISTS (SELECT 1 FROM cases c WHERE c.workspace_id = feedback.workspace_id
                            AND c.id = feedback.case_id AND c.requester_contact_id = {contact})
            ))"""
        elif table == "customer_imports":
            privileged = f"""EXISTS (
                SELECT 1 FROM memberships m WHERE m.workspace_id = customer_imports.workspace_id
                AND m.user_id = {user} AND m.active AND m.role IN ('admin','manager')
            )"""
            uploader = f"""EXISTS (
                SELECT 1 FROM memberships m WHERE m.workspace_id = customer_imports.workspace_id
                AND m.id = customer_imports.submitted_by_member_id AND m.user_id = {user} AND m.active
            )"""
            read = f"({staff} AND (current_user = 'atlas_migrator' OR {privileged} OR {uploader}))"
            write = f"({staff} AND (current_user = 'atlas_migrator' OR {privileged}))"
        op.execute(f"CREATE POLICY m3_read ON {table} FOR SELECT USING ({scope} AND ({read}))")
        op.execute(
            f"CREATE POLICY m3_insert ON {table} FOR INSERT WITH CHECK ({scope} AND ({write}))"
        )
        if table != "feedback":
            op.execute(
                f"CREATE POLICY m3_update ON {table} FOR UPDATE USING ({scope} AND ({write})) WITH CHECK ({scope} AND ({write}))"
            )
        op.execute(
            f"CREATE POLICY m3_operator_cleanup ON {table} FOR DELETE TO atlas_migrator USING ({scope})"
        )
        grants = "SELECT, INSERT" if table == "feedback" else "SELECT, INSERT, UPDATE"
        op.execute(f"GRANT {grants} ON {table} TO atlas_app")


def downgrade() -> None:
    for table in ("customer_imports", "tasks", "feedback"):
        op.drop_table(table)
    op.drop_constraint("uq_case_requester_reference", "cases", type_="unique")
    op.drop_constraint("uq_case_customer_reference", "cases", type_="unique")
