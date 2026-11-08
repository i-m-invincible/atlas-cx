"""Verify an existing M0 workspace survives the M1 upgrade in an expendable CI DB."""

import os
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.platform.database import build_engine

config = Config("alembic.ini")
command.upgrade(config, "0001_workspace_boundary")
engine = build_engine(os.environ["MIGRATION_DATABASE_URL"])
identifier = uuid4()
with engine.begin() as connection:
    connection.execute(
        text("SELECT set_config('app.workspace_id', :scope, true)"), {"scope": str(identifier)}
    )
    connection.execute(
        text(
            "INSERT INTO workspaces(id, slug, name, timezone, version) "
            "VALUES (:id, :slug, 'M0 upgrade fixture', 'Asia/Kolkata', 1)"
        ),
        {"id": identifier, "slug": f"upgrade-{identifier}"},
    )
command.upgrade(config, "head")
with engine.begin() as connection:
    connection.execute(
        text("SELECT set_config('app.workspace_id', :scope, true)"), {"scope": str(identifier)}
    )
    row = connection.execute(
        text("SELECT name, timezone, version, is_demo FROM workspaces WHERE id=:id"),
        {"id": identifier},
    ).one()
    assert row == ("M0 upgrade fixture", "Asia/Kolkata", 1, False)
    connection.execute(text("DELETE FROM workspaces WHERE id=:id"), {"id": identifier})
engine.dispose()
print("Verified M0 workspace preservation during M1 upgrade")
