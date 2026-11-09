"""Verify an existing M2 case survives the additive M3 migration in CI."""

import json
import os
import runpy
from pathlib import Path
from uuid import UUID

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.platform.database import build_engine, workspace_session
from scripts.seed_m2_browser import main as seed_cases

config = Config("alembic.ini")
command.downgrade(config, "0004_case_workflow")
runpy.run_module("scripts.seed_m1_browser", run_name="__main__")
seed_cases()
fixture_path = Path(__file__).resolve().parents[2] / "tmp" / "m2-browser.json"
fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
case_id = UUID(fixture["other_case_id"])
migrator = build_engine(os.environ["MIGRATION_DATABASE_URL"])
with migrator.begin() as connection:
    connection.execute(
        text("SELECT set_config('app.login_workspace', :slug, true)"),
        {"slug": fixture["other_workspace"]},
    )
    workspace_id = connection.scalar(
        text("SELECT id FROM workspaces WHERE slug = :slug"), {"slug": fixture["other_workspace"]}
    )
    assert workspace_id
migrator.dispose()
application = build_engine(os.environ["TEST_DATABASE_URL"])


def snapshot() -> tuple[object, ...]:
    with workspace_session(application, workspace_id) as session:
        result = session.execute(
            text(
                "SELECT c.number,c.state,c.config_version_id,c.resolution_target_seconds,"
                "m.body,cc.target_seconds FROM cases c "
                "JOIN messages m ON m.workspace_id=c.workspace_id AND m.case_id=c.id "
                "JOIN case_cycles cc ON cc.workspace_id=c.workspace_id AND cc.case_id=c.id "
                "WHERE c.id=:id AND m.message_kind='initial' AND cc.cycle_number=1"
            ),
            {"id": case_id},
        ).one()
        return tuple(result)


before = snapshot()
command.upgrade(config, "head")
assert snapshot() == before
application.dispose()
print("Verified M2 case, pinned configuration, initial message and cycle preservation")
