"""Verify a frozen M1 identity/customer/session fixture survives M2 in a disposable CI DB."""

import os
import secrets
from datetime import timedelta
from uuid import uuid4

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from alembic import command
from app.main import create_app
from app.modules.identity.security import digest, password_hash
from app.platform.database import build_engine
from app.platform.protocol import now

config = Config("alembic.ini")
command.downgrade(config, "0003_setup_acceptance")
migration = build_engine(os.environ["MIGRATION_DATABASE_URL"])
workspace, user, member, customer, contact, session_id = [uuid4() for _ in range(6)]
raw = secrets.token_urlsafe(32)
instant = now()
params = {
    "workspace": workspace,
    "user": user,
    "member": member,
    "customer": customer,
    "contact": contact,
    "session": session_id,
    "slug": f"m1-upgrade-{workspace}",
    "email": f"upgrade-{user}@example.com",
    "hash": password_hash(secrets.token_urlsafe(24)),
    "token_hash": digest(raw),
    "csrf_hash": digest(secrets.token_urlsafe(32)),
    "instant": instant,
    "idle": instant + timedelta(hours=12),
    "absolute": instant + timedelta(days=7),
}
with migration.begin() as connection:
    connection.execute(
        text("SELECT set_config('app.workspace_id', :scope, true)"), {"scope": str(workspace)}
    )
    connection.execute(text("SELECT set_config('app.audience', 'staff', true)"))
    # Frozen SQL deliberately avoids the current ORM's M2 columns.
    for statement in (
        "INSERT INTO workspaces(id,slug,name,timezone,version,is_demo) "
        "VALUES (:workspace,:slug,'M1 upgrade fixture','Asia/Kolkata',1,false)",
        "INSERT INTO users(id,normalized_email,display_name,password_hash) "
        "VALUES (:user,:email,'M1 preserved operator',:hash)",
        "INSERT INTO memberships(id,workspace_id,user_id,role,active,version,setup_completed_at) "
        "VALUES (:member,:workspace,:user,'admin',true,1,:instant)",
        "UPDATE workspaces SET feedback_manager_member_id=:member WHERE id=:workspace",
        "INSERT INTO customers(id,workspace_id,name,kind,lifecycle,external_id,owner_member_id,"
        "tags,activity_expected,version) VALUES (:customer,:workspace,'Preserved customer',"
        "'business','active','m1-upgrade-customer',:member,ARRAY['preserved'],false,1)",
        "INSERT INTO contacts(id,workspace_id,customer_id,name,normalized_email,version) "
        "VALUES (:contact,:workspace,:customer,'Preserved contact',:email,1)",
        "INSERT INTO sessions(id,token_hash,csrf_secret_hash,user_id,workspace_id,audience,"
        "expires_at,absolute_expires_at,last_seen_at) "
        "VALUES (:session,:token_hash,:csrf_hash,:user,:workspace,"
        "'staff',:idle,:absolute,:instant)",
    ):
        connection.execute(text(statement), params)
command.upgrade(config, "head")
application = create_app()
application.state.engine.dispose()
application.state.engine = build_engine(os.environ["TEST_DATABASE_URL"])
with TestClient(application, base_url="https://testserver") as client:
    client.cookies.set("atlas_session", raw)
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["data"]["user_id"] == str(user)
    record = client.get(f"/api/v1/customers/{customer}").json()["data"]
    assert record["name"] == "Preserved customer" and record["owner_member_id"] == str(member)
    assert client.get(f"/api/v1/contacts/{contact}").status_code == 200
    configs = client.get("/api/v1/case-configs").json()["data"]
    assert len(configs) == 1 and configs[0]["status"] == "published"
    assert client.get("/api/v1/cases").json()["data"] == []
with migration.begin() as connection:
    connection.execute(
        text("SELECT set_config('app.workspace_id', :scope, true)"), {"scope": str(workspace)}
    )
    connection.execute(text("SELECT set_config('app.audience', 'staff', true)"))
    connection.execute(
        text(
            "UPDATE workspaces SET active_case_config_id=NULL, feedback_manager_member_id=NULL "
            "WHERE id=:workspace"
        ),
        params,
    )
    for table in (
        "case_config_versions",
        "workspace_counters",
        "sessions",
        "contacts",
        "customers",
        "memberships",
    ):
        connection.execute(text(f"DELETE FROM {table} WHERE workspace_id=:workspace"), params)
    connection.execute(text("DELETE FROM workspaces WHERE id=:workspace"), params)
    connection.execute(text("DELETE FROM users WHERE id=:user"), params)
migration.dispose()
print("Verified M1 customer, contact, membership and opaque session preservation during M2 upgrade")
