"""Verify M3 follow-ups and staged imports survive the additive M4 migration."""

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.platform.database import build_engine, workspace_session

config = Config("alembic.ini")
command.downgrade(config, "0005_followups_imports")
fixture = json.loads(
    (Path(__file__).resolve().parents[2] / "tmp" / "m2-browser.json").read_text(encoding="utf-8")
)
case_id = UUID(fixture["other_case_id"])
migration = build_engine(os.environ["MIGRATION_DATABASE_URL"])
with migration.begin() as connection:
    connection.execute(
        text("SELECT set_config('app.login_workspace', :slug, true)"),
        {"slug": fixture["other_workspace"]},
    )
    workspace = connection.scalar(
        text("SELECT id FROM workspaces WHERE slug = :slug"), {"slug": fixture["other_workspace"]}
    )
    assert workspace
task, stage = uuid4(), uuid4()
with workspace_session(migration, workspace) as db:
    member = db.scalar(text("SELECT id FROM memberships WHERE active AND role = 'admin' LIMIT 1"))
    customer = db.scalar(text("SELECT customer_id FROM cases WHERE id = :case"), {"case": case_id})
    assert member and customer
    values = {
        "workspace": workspace,
        "case": case_id,
        "customer": customer,
        "member": member,
        "task": task,
        "stage": stage,
    }
    db.execute(
        text("""
        INSERT INTO tasks (id, workspace_id, customer_id, case_id, title, assignee_member_id,
            state, due_at, version)
        VALUES (:task, :workspace, :customer, :case, 'Synthetic migration follow-up',
            :member, 'open', now() + interval '1 day', 1)
    """),
        values,
    )
    db.execute(
        text("""
        INSERT INTO customer_imports (id, workspace_id, submitted_by_member_id, status,
            input_hash, normalized_rows_json, row_results_json, create_count, update_count,
            error_count, expires_at, version)
        VALUES (:stage, :workspace, :member, 'validated', repeat('a',64),
            '[{"name":"Synthetic staged customer"}]', '[]', 1, 0, 0, now() + interval '1 day', 1)
    """),
        values,
    )
    user = db.scalar(text("SELECT user_id FROM memberships WHERE id = :member"), values)
    assert user
migration.dispose()
app = build_engine(os.environ["TEST_DATABASE_URL"])


def snapshot() -> tuple[object, ...]:
    with workspace_session(app, workspace, user_id=user) as db:
        assert db.scalar(text("SELECT current_user")) == "atlas_app"
        return tuple(
            db.execute(
                text("""
            SELECT t.case_id, t.title, t.state, t.due_at, t.version,
                i.status, i.normalized_rows_json, i.create_count, i.expires_at
            FROM tasks t CROSS JOIN customer_imports i
            WHERE t.id = :task AND i.id = :stage
        """),
                values,
            ).one()
        )


before = snapshot()
command.upgrade(config, "head")
assert snapshot() == before
app.dispose()
print("Verified M3 follow-up and staged import preservation as atlas_app")
