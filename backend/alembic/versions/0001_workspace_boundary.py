"""Workspace root and fail-closed row security.

Extension and roles are operator-provisioned, not created by the API.
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_workspace_boundary"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_workspace_version"),
    )
    op.execute("ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspaces FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY workspace_scope ON workspaces "
        "USING (id = NULLIF(current_setting('app.workspace_id', true), '')::uuid) "
        "WITH CHECK (id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON workspaces TO atlas_app")
    op.execute("GRANT SELECT ON alembic_version TO atlas_app")


def downgrade() -> None:
    op.drop_table("workspaces")
