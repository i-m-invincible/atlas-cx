"""Require verified setup before staff or portal access can be activated."""

import sqlalchemy as sa

from alembic import op

revision = "0003_setup_acceptance"
down_revision = "0002_identity_customers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FORCE RLS applies to the owner. A temporary migration-role-only policy
    # permits backfilling existing active M1 identities in this DDL transaction.
    for table in ("memberships", "portal_bindings"):
        op.add_column(table, sa.Column("setup_completed_at", sa.DateTime(timezone=True)))
        op.execute(sa.text("SELECT set_config('app.login_workspace', '', true)"))
        op.execute(
            f"CREATE POLICY m1_acceptance_backfill ON {table} TO atlas_migrator "
            "USING (true) WITH CHECK (true)"
        )
        op.execute(f"UPDATE {table} SET setup_completed_at = created_at WHERE active")
        op.execute(f"DROP POLICY m1_acceptance_backfill ON {table}")
        op.create_check_constraint(
            f"ck_{table}_accepted_access", table, "NOT active OR setup_completed_at IS NOT NULL"
        )


def downgrade() -> None:
    for table in ("portal_bindings", "memberships"):
        op.drop_constraint(f"ck_{table}_accepted_access", table, type_="check")
        op.drop_column(table, "setup_completed_at")
