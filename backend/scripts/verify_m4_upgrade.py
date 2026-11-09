"""Verify recorded activity survives the additive M5 migration."""

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.platform.database import build_engine, set_scope, workspace_session

config = Config("alembic.ini")
command.downgrade(config, "0006_activity_analytics")
fixture = json.loads(
    (Path(__file__).resolve().parents[2] / "tmp" / "m2-browser.json").read_text(encoding="utf-8")
)
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
definition, event = uuid4(), uuid4()
with workspace_session(migration, workspace) as db:
    customer = db.scalar(
        text("SELECT customer_id FROM cases WHERE id = :case"),
        {"case": UUID(fixture["other_case_id"])},
    )
    assert customer
    values = {
        "workspace": workspace,
        "customer": customer,
        "definition": definition,
        "event": event,
    }
    db.execute(
        text("""
        INSERT INTO event_definitions (id, workspace_id, key, label, allowed_properties_json,
            counts_as_activity, enabled, version)
        VALUES (:definition, :workspace, 'synthetic_m4_upgrade', 'Synthetic retained activity',
            '{}', true, true, 1)
    """),
        values,
    )
    set_scope(db, workspace, "ingest")
    db.execute(text("SELECT set_config('app.ingest_credential', :id, true)"), {"id": str(uuid4())})
    db.execute(
        text("""
        INSERT INTO customer_events (id, workspace_id, customer_id, event_definition_id,
            external_event_id, occurred_at, received_at, safe_properties, payload_hash,
            activity_flag_snapshot)
        VALUES (:event, :workspace, :customer, :definition, 'synthetic-m4-upgrade',
            now(), now(), '{}', repeat('a', 64), true)
    """),
        values,
    )
migration.dispose()
app = build_engine(os.environ["TEST_DATABASE_URL"])


def snapshot() -> tuple[object, ...]:
    with workspace_session(app, workspace) as db:
        assert db.scalar(text("SELECT current_user")) == "atlas_app"
        return tuple(
            db.execute(
                text("""
            SELECT e.customer_id, d.key, e.external_event_id, e.occurred_at, e.received_at,
                e.payload_hash, e.activity_flag_snapshot
            FROM customer_events e JOIN event_definitions d
                ON (e.workspace_id, e.event_definition_id) = (d.workspace_id, d.id)
            WHERE e.id = :event
        """),
                values,
            ).one()
        )


before = snapshot()
command.upgrade(config, "head")
assert snapshot() == before
app.dispose()
print("Verified M4 recorded activity preservation as atlas_app")
