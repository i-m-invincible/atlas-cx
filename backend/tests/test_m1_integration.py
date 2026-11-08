import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.cases.models import (
    Case,
    CaseCycle,
    CaseTransition,
    Message,
    ReadMarker,
    WorkspaceCounter,
)
from app.modules.customers.models import Contact, Customer
from app.modules.identity.models import (
    LoginSession,
    Membership,
    PortalBinding,
    SetupToken,
    User,
)
from app.modules.identity.operator import bootstrap_workspace
from app.modules.identity.security import SESSION_COOKIE, digest, password_hash
from app.modules.identity.service import issue_setup
from app.modules.workspace.case_config_models import CaseConfig
from app.modules.workspace.models import Workspace
from app.modules.workspace.team_models import Team, TeamMember
from app.platform.audit import AuditEvent
from app.platform.config import get_settings
from app.platform.database import build_engine, workspace_session
from app.platform.idempotency import IdempotencyRecord
from app.platform.protocol import now

pytestmark = pytest.mark.integration
PASSWORD = "Fictional-test-password-42"


@dataclass
class Core:
    app_url: str
    migration_url: str
    workspaces: list[UUID] = field(default_factory=list)
    actors: dict[str, dict[str, Any]] = field(default_factory=dict)
    records: dict[str, UUID] = field(default_factory=dict)


@pytest.fixture(scope="module")
def core() -> Iterator[Core]:
    app_url = os.environ.get("TEST_DATABASE_URL")
    migration_url = os.environ.get("MIGRATION_DATABASE_URL")
    assert app_url and migration_url, "Real PostgreSQL test URLs are required"
    value = Core(app_url, migration_url)
    engine = build_engine(migration_url)
    hashed = password_hash(PASSWORD)
    for number in (1, 2):
        marker = uuid4().hex[:12]
        with Session(engine) as session, session.begin():
            workspace, admin = bootstrap_workspace(
                session,
                f"m1-{marker}",
                f"Synthetic workspace {number}",
                f"admin-{marker}@example.com",
                "Synthetic administrator",
                PASSWORD,
            )
            value.workspaces.append(workspace.id)
            value.actors[f"admin{number}"] = {
                "workspace": workspace.slug,
                "email": f"admin-{marker}@example.com",
                "member": admin.id,
                "user": admin.user_id,
            }
            for role in ("agent", "manager", "viewer"):
                user = User(
                    normalized_email=f"{role}-{marker}@example.com",
                    display_name=f"Synthetic {role}",
                    password_hash=hashed,
                )
                session.add(user)
                session.flush()
                member = Membership(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role=role,
                    active=True,
                    setup_completed_at=now(),
                )
                session.add(member)
                session.flush()
                value.actors[f"{role}{number}"] = {
                    "workspace": workspace.slug,
                    "email": user.normalized_email,
                    "member": member.id,
                    "user": user.id,
                }
            customer = Customer(
                workspace_id=workspace.id, name=f"Synthetic customer {number}", kind="business"
            )
            session.add(customer)
            session.flush()
            value.records[f"customer{number}"] = customer.id
            for suffix in ("a", "b"):
                user = User(
                    normalized_email=f"contact-{suffix}-{marker}@example.com",
                    display_name=f"Synthetic contact {suffix}",
                    password_hash=hashed,
                )
                session.add(user)
                contact = Contact(
                    workspace_id=workspace.id,
                    customer_id=customer.id,
                    name=f"Synthetic contact {suffix}",
                    normalized_email=user.normalized_email,
                )
                session.add(contact)
                session.flush()
                session.add(
                    PortalBinding(
                        workspace_id=workspace.id,
                        contact_id=contact.id,
                        user_id=user.id,
                        active=True,
                        setup_completed_at=now(),
                    )
                )
                value.actors[f"portal{suffix}{number}"] = {
                    "workspace": workspace.slug,
                    "email": user.normalized_email,
                    "contact": contact.id,
                    "user": user.id,
                }
    yield value
    # Only the migration owner cleans this disposable fixture. The API cannot delete history.
    candidate_users: set[UUID] = set()
    for workspace_id in value.workspaces:
        with workspace_session(engine, workspace_id) as session:
            candidate_users.update(session.scalars(select(Membership.user_id)))
            candidate_users.update(session.scalars(select(PortalBinding.user_id)))
            workspace = session.get(Workspace, workspace_id)
            assert workspace
            workspace.feedback_manager_member_id = None
            workspace.active_case_config_id = None
            session.flush()
            session.execute(delete(SetupToken).where(SetupToken.workspace_id == workspace_id))
            session.execute(delete(LoginSession).where(LoginSession.workspace_id == workspace_id))
            for model in (
                IdempotencyRecord,
                ReadMarker,
                CaseTransition,
                Message,
                CaseCycle,
                Case,
                CaseConfig,
                WorkspaceCounter,
                AuditEvent,
                TeamMember,
                Team,
                PortalBinding,
                Contact,
                Customer,
                Membership,
            ):
                session.execute(delete(model))
            session.delete(workspace)
            # A user can be shared across workspaces; remove global rows only after both are gone.
    with Session(engine) as session, session.begin():
        orphan_users = select(User.id).where(
            User.id.in_(candidate_users),
            ~User.id.in_(select(Membership.user_id)),
            ~User.id.in_(select(PortalBinding.user_id)),
        )
        session.execute(delete(SetupToken).where(SetupToken.user_id.in_(orphan_users)))
        session.execute(delete(LoginSession).where(LoginSession.user_id.in_(orphan_users)))
        session.execute(delete(User).where(User.id.in_(orphan_users)))
    engine.dispose()


@pytest.fixture
def clients(core: Core) -> Iterator[Any]:
    opened = []

    def client_for(actor: str | None = "admin1") -> TestClient:
        application = create_app()
        application.state.engine.dispose()
        application.state.engine = build_engine(core.app_url)
        client = TestClient(application, base_url="https://testserver")
        client.__enter__()
        opened.append(client)
        if actor:
            account = core.actors[actor]
            response = mutate(
                client,
                "/auth/login",
                {
                    "workspace_slug": account["workspace"],
                    "audience": "portal" if actor.startswith("portal") else "staff",
                    "email": account["email"],
                    "password": PASSWORD,
                },
            )
            assert response.status_code == 200, response.text
        return client

    yield client_for
    for client in opened:
        client.__exit__(None, None, None)


def csrf(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return {
        "Origin": get_settings().public_origin,
        "X-CSRF-Token": response.json()["data"]["csrf_token"],
    }


def mutate(
    client: TestClient,
    path: str,
    body: object = None,
    method: str = "POST",
    version: int | None = None,
) -> Any:
    headers = csrf(client)
    if version is not None:
        headers["If-Match"] = f'"{version}"'
    return client.request(method, "/api/v1" + path, headers=headers, json=body)


def new_customer(client: TestClient, **changes: Any) -> dict[str, Any]:
    response = mutate(
        client,
        "/customers",
        {"name": f"Synthetic {uuid4().hex[:12]}", "kind": "business", **changes},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def setup_member(client: TestClient, core: Core, role: str = "agent") -> dict[str, Any]:
    email = f"new-{uuid4().hex}@example.com"
    response = mutate(
        client, "/members", {"email": email, "display_name": "Synthetic new member", "role": role}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_actual_app_role_and_tenant_policies(core: Core) -> None:
    engine = build_engine(core.app_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_user")) == "atlas_app"
        assert connection.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        ).one() == (False, False)
        assert connection.execute(text("SELECT id FROM customers")).all() == []
        assert connection.execute(text("SELECT id FROM contacts")).all() == []
    with workspace_session(engine, core.workspaces[0]) as session:
        assert core.records["customer1"] in session.scalars(select(Customer.id)).all()
        assert session.get(Customer, core.records["customer2"]) is None
    engine.dispose()


def test_login_cookie_rotation_hashed_storage_and_logout(core: Core, clients: Any) -> None:
    client = clients()
    first = client.cookies.get(SESSION_COOKIE)
    account = core.actors["admin1"]
    response = mutate(
        client,
        "/auth/login",
        {
            "workspace_slug": account["workspace"],
            "audience": "staff",
            "email": account["email"],
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert all(flag in cookie for flag in ("Secure", "HttpOnly", "SameSite=lax"))
    second = client.cookies.get(SESSION_COOKIE)
    assert first and second and first != second
    engine = build_engine(core.migration_url)
    with Session(engine) as session:
        old = session.scalar(select(LoginSession).where(LoginSession.token_hash == digest(first)))
        stored = session.scalar(
            select(LoginSession).where(LoginSession.token_hash == digest(second))
        )
        assert old and old.revoked_at
        assert stored and stored.token_hash != second and len(stored.token_hash) == 64
    assert mutate(client, "/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    engine.dispose()


@pytest.mark.parametrize("expiry", ["expires_at", "absolute_expires_at"])
def test_session_expiration(core: Core, clients: Any, expiry: str) -> None:
    client = clients()
    raw = client.cookies.get(SESSION_COOKIE)
    assert raw
    engine = build_engine(core.migration_url)
    with Session(engine) as session, session.begin():
        session.execute(
            update(LoginSession)
            .where(LoginSession.token_hash == digest(raw))
            .values(**{expiry: now() - timedelta(seconds=1)})
        )
    assert client.get("/api/v1/auth/me").status_code == 401
    engine.dispose()


@pytest.mark.parametrize("kind", ["missing", "forged", "origin"])
def test_csrf_and_origin_protect_mutations(core: Core, clients: Any, kind: str) -> None:
    client = clients()
    headers = csrf(client)
    if kind == "missing":
        headers.pop("X-CSRF-Token")
    elif kind == "forged":
        headers["X-CSRF-Token"] = "forged"
    else:
        headers["Origin"] = "https://other.example"
    response = client.post(
        "/api/v1/customers", headers=headers, json={"name": "Must not persist", "kind": "business"}
    )
    assert response.status_code == 403


def test_customer_and_contact_crud_etags_and_audit(core: Core, clients: Any) -> None:
    client = clients()
    customer = new_customer(
        client,
        external_id=f"external-{uuid4()}",
        tags=["pilot"],
        owner_member_id=str(core.actors["agent1"]["member"]),
    )
    detail = client.get(f"/api/v1/customers/{customer['id']}")
    assert detail.headers["etag"] == '"1"'
    missing = mutate(client, f"/customers/{customer['id']}", {"name": "Changed"}, "PATCH")
    assert missing.status_code == 428
    updated = mutate(
        client,
        f"/customers/{customer['id']}",
        {"name": "Changed", "owner_member_id": None},
        "PATCH",
        1,
    )
    assert updated.status_code == 200 and updated.json()["data"]["version"] == 2
    stale = mutate(client, f"/customers/{customer['id']}", {"name": "Stale overwrite"}, "PATCH", 1)
    assert stale.status_code == 409 and stale.json()["code"] == "version_conflict"
    contact = mutate(
        client,
        "/contacts",
        {
            "customer_id": customer["id"],
            "name": "Synthetic contact",
            "email": f"contact-{uuid4()}@example.com",
        },
    )
    assert contact.status_code == 201, contact.text
    data = contact.json()["data"]
    edited = mutate(client, f"/contacts/{data['id']}", {"phone": "12345"}, "PATCH", 1)
    assert edited.status_code == 200 and edited.json()["data"]["phone"] == "12345"
    archived = mutate(
        client,
        f"/customers/{customer['id']}/archive",
        {"reason": "Synthetic archive test"},
        version=2,
    )
    assert archived.status_code == 200 and archived.json()["data"]["archived_at"]
    audit = client.get("/api/v1/audit?limit=100").json()["data"]
    actions = {event["action"] for event in audit if event["entity_id"] == customer["id"]}
    assert {"customer.created", "customer.updated", "customer.archived"} <= actions


def test_search_filters_pagination_and_cursor_scope(core: Core, clients: Any) -> None:
    client = clients()
    marker = "Page-" + uuid4().hex[:10]
    for suffix in ("A", "B", "C"):
        new_customer(client, name=marker + suffix, lifecycle="prospect", tags=["pagination"])
    first = client.get(
        f"/api/v1/customers?q={marker}&lifecycle=prospect&tag=pagination&sort=name&limit=2"
    ).json()
    assert len(first["data"]) == 2 and first["meta"]["has_more"]
    cursor = first["meta"]["next_cursor"]
    second = client.get(
        "/api/v1/customers",
        params={
            "q": marker,
            "lifecycle": "prospect",
            "tag": "pagination",
            "sort": "name",
            "limit": 2,
            "cursor": cursor,
        },
    ).json()
    assert len(second["data"]) == 1 and not second["meta"]["has_more"]
    assert len({row["id"] for row in first["data"] + second["data"]}) == 3
    assert (
        client.get("/api/v1/customers", params={"q": "changed", "cursor": cursor}).status_code
        == 400
    )
    other = clients("admin2")
    assert (
        other.get(
            "/api/v1/customers",
            params={
                "q": marker,
                "lifecycle": "prospect",
                "tag": "pagination",
                "sort": "name",
                "cursor": cursor,
            },
        ).status_code
        == 400
    )


def test_cross_workspace_reads_writes_and_references(core: Core, clients: Any) -> None:
    client = clients()
    other = core.records["customer2"]
    assert client.get(f"/api/v1/customers/{other}").status_code == 404
    assert (
        mutate(client, f"/customers/{other}", {"name": "forbidden"}, "PATCH", 1).status_code == 404
    )
    assert (
        mutate(
            client,
            "/contacts",
            {
                "customer_id": str(other),
                "name": "forbidden",
                "email": f"forbidden-{uuid4()}@example.com",
            },
        ).status_code
        == 404
    )
    assert (
        mutate(
            client,
            "/customers",
            {
                "name": "forbidden owner",
                "kind": "business",
                "owner_member_id": str(core.actors["agent2"]["member"]),
            },
        ).status_code
        == 422
    )
    assert client.get(
        "/api/v1/auth/me", headers={"X-Workspace-ID": str(core.workspaces[1])}
    ).json()["data"]["workspace_id"] == str(core.workspaces[0])


def test_viewer_and_portal_cannot_write_or_administer(core: Core, clients: Any) -> None:
    viewer = clients("viewer1")
    assert viewer.get("/api/v1/customers").status_code == 200
    assert (
        mutate(viewer, "/customers", {"name": "forbidden", "kind": "business"}).status_code == 403
    )
    assert mutate(viewer, "/teams", {"name": "forbidden", "member_ids": []}).status_code == 403
    assert viewer.get("/api/v1/audit").status_code == 403
    portal = clients("portala1")
    for path in ("/customers", "/contacts", "/members", "/teams", "/workspace", "/audit"):
        assert portal.get("/api/v1" + path).status_code == 403


def test_same_customer_contacts_are_isolated_by_rls(core: Core, clients: Any) -> None:
    actor = core.actors["portala1"]
    other = core.actors["portalb1"]
    client = clients("portala1")
    me = client.get("/api/v1/auth/me").json()["data"]
    assert me["contact_id"] == str(actor["contact"]) and str(other["contact"]) not in str(me)
    engine = build_engine(core.app_url)
    with workspace_session(
        engine, core.workspaces[0], "portal", actor["user"], actor["contact"]
    ) as session:
        assert session.scalars(select(Contact.id)).all() == [actor["contact"]]
        assert session.get(Contact, other["contact"]) is None
        assert session.scalars(select(Customer.id)).all() == []
        assert session.scalars(select(PortalBinding.user_id)).all() == [actor["user"]]
        assert (
            session.execute(
                update(Contact).where(Contact.id == actor["contact"]).values(name="forbidden")
            ).rowcount
            == 0
        )
    engine.dispose()


def test_setup_links_are_single_use_and_do_not_log_in(core: Core, clients: Any) -> None:
    admin = clients()
    data = setup_member(admin, core)
    raw = data["setup_url"].split("#token=")[1]
    anonymous = clients(None)
    response = mutate(anonymous, "/auth/setup", {"setup_token": raw, "new_password": PASSWORD})
    assert response.status_code == 200, response.text
    assert not anonymous.cookies.get(SESSION_COOKIE)
    assert (
        mutate(anonymous, "/auth/setup", {"setup_token": raw, "new_password": PASSWORD}).status_code
        == 400
    )
    engine = build_engine(core.migration_url)
    with Session(engine) as session:
        stored = session.scalar(select(SetupToken).where(SetupToken.token_hash == digest(raw)))
        assert stored and stored.used_at and stored.token_hash != raw
    engine.dispose()


def test_existing_account_setup_requires_existing_password(core: Core, clients: Any) -> None:
    admin = clients()
    existing = core.actors["admin2"]
    data = mutate(
        admin,
        "/members",
        {
            "email": existing["email"],
            "display_name": "Must not replace global name",
            "role": "viewer",
        },
    ).json()["data"]
    assert data["member"]["display_name"] == "Must not replace global name"
    # A global password proves account existence, not acceptance of this invitation.
    assert (
        mutate(
            admin,
            f"/members/{data['member']['id']}",
            {"active": True},
            "PATCH",
            data["member"]["version"],
        ).status_code
        == 409
    )
    raw = data["setup_url"].split("#token=")[1]
    anonymous = clients(None)
    assert (
        mutate(
            anonymous, "/auth/setup", {"setup_token": raw, "new_password": "attacker-new-password"}
        ).status_code
        == 400
    )
    assert (
        mutate(
            anonymous, "/auth/setup", {"setup_token": raw, "current_password": PASSWORD}
        ).status_code
        == 200
    )
    assert (
        clients("admin2").get("/api/v1/auth/me").json()["data"]["display_name"]
        == "Synthetic administrator"
    )


def test_setup_expiry_and_reissue(core: Core, clients: Any) -> None:
    admin = clients()
    data = setup_member(admin, core)
    raw = data["setup_url"].split("#token=")[1]
    engine = build_engine(core.migration_url)
    with Session(engine) as session, session.begin():
        session.execute(
            update(SetupToken)
            .where(SetupToken.token_hash == digest(raw))
            .values(expires_at=now() - timedelta(seconds=1))
        )
    anonymous = clients(None)
    assert (
        mutate(anonymous, "/auth/setup", {"setup_token": raw, "new_password": PASSWORD}).status_code
        == 400
    )
    member = data["member"]
    reissued = mutate(
        admin,
        "/members",
        {"email": member["email"], "display_name": member["display_name"], "role": "agent"},
        version=member["version"],
    )
    assert reissued.status_code == 201, reissued.text
    assert reissued.json()["data"]["setup_url"] != data["setup_url"]
    engine.dispose()


def test_portal_provisioning_and_disable_take_effect(core: Core, clients: Any) -> None:
    admin = clients()
    customer = new_customer(admin)
    email = f"portal-new-{uuid4()}@example.com"
    contact = mutate(
        admin,
        "/contacts",
        {"customer_id": customer["id"], "name": "Synthetic portal contact", "email": email},
    ).json()["data"]
    response = mutate(admin, f"/contacts/{contact['id']}/portal-access", version=1)
    assert response.status_code == 200, response.text
    raw = response.json()["data"]["setup_url"].split("#token=")[1]
    portal = clients(None)
    assert (
        mutate(portal, "/auth/setup", {"setup_token": raw, "new_password": PASSWORD}).status_code
        == 200
    )
    account = core.actors["admin1"]
    assert (
        mutate(
            portal,
            "/auth/login",
            {
                "workspace_slug": account["workspace"],
                "audience": "portal",
                "email": email,
                "password": PASSWORD,
            },
        ).status_code
        == 200
    )
    assert portal.get("/api/v1/auth/me").json()["data"]["contact_id"] == contact["id"]
    bound = mutate(
        admin, f"/contacts/{contact['id']}", {"email": f"changed-{uuid4()}@example.com"}, "PATCH", 2
    )
    assert bound.status_code == 409
    assert (
        mutate(
            admin, f"/contacts/{contact['id']}/portal-access", {"active": False}, "PATCH", 2
        ).status_code
        == 200
    )
    assert portal.get("/api/v1/auth/me").status_code == 401


def test_password_change_revokes_all_sessions(core: Core, clients: Any) -> None:
    admin = clients()
    data = setup_member(admin, core)
    raw = data["setup_url"].split("#token=")[1]
    first, second = clients(None), clients(None)
    assert (
        mutate(first, "/auth/setup", {"setup_token": raw, "new_password": PASSWORD}).status_code
        == 200
    )
    login_body = {
        "workspace_slug": core.actors["admin1"]["workspace"],
        "audience": "staff",
        "email": data["member"]["email"],
        "password": PASSWORD,
    }
    assert mutate(first, "/auth/login", login_body).status_code == 200
    assert mutate(second, "/auth/login", login_body).status_code == 200
    assert (
        mutate(
            first,
            "/auth/password",
            {"current_password": PASSWORD, "new_password": "Another-fictional-password-55"},
        ).status_code
        == 200
    )
    assert first.get("/api/v1/auth/me").status_code == 401
    assert second.get("/api/v1/auth/me").status_code == 401


def test_teams_constraints_and_admin_safeguards(core: Core, clients: Any) -> None:
    admin = clients()
    created = mutate(
        admin,
        "/teams",
        {"name": f"Synthetic team {uuid4()}", "member_ids": [str(core.actors["agent1"]["member"])]},
    )
    assert created.status_code == 201, created.text
    team = created.json()["data"]
    assert team["member_ids"] == [str(core.actors["agent1"]["member"])]
    assert (
        mutate(
            admin,
            f"/teams/{team['id']}",
            {"member_ids": [str(core.actors["agent2"]["member"])]},
            "PATCH",
            1,
        ).status_code
        == 422
    )
    administrator = core.actors["admin1"]["member"]
    assert (
        mutate(admin, f"/members/{administrator}", {"active": False}, "PATCH", 1).status_code == 409
    )
    assert clients("agent1").get("/api/v1/teams").status_code == 200


def test_database_constraints_and_append_only_audit(core: Core) -> None:
    engine = build_engine(core.app_url)
    with pytest.raises(DBAPIError), workspace_session(engine, core.workspaces[0]) as session:
        session.add(
            Contact(
                workspace_id=core.workspaces[0],
                customer_id=core.records["customer2"],
                name="Forbidden",
                normalized_email=f"bad-{uuid4()}@example.com",
            )
        )
        session.flush()
    with pytest.raises(DBAPIError), workspace_session(engine, core.workspaces[0]) as session:
        session.execute(delete(Customer).where(Customer.id == core.records["customer1"]))
    with pytest.raises(DBAPIError), workspace_session(engine, core.workspaces[0]) as session:
        session.execute(update(AuditEvent).values(action="forged"))
    engine.dispose()


def test_duplicate_customer_rolls_back_audit(core: Core, clients: Any) -> None:
    client = clients()
    external = f"duplicate-{uuid4()}"
    new_customer(client, external_id=external)
    engine = build_engine(core.migration_url)
    with workspace_session(engine, core.workspaces[0]) as session:
        before = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "customer.created")
        )
    response = mutate(
        client, "/customers", {"name": "Duplicate", "kind": "business", "external_id": external}
    )
    assert response.status_code == 409
    with workspace_session(engine, core.workspaces[0]) as session:
        after = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "customer.created")
        )
    assert before == after
    engine.dispose()


def test_setup_consumption_is_atomic_under_race(core: Core, clients: Any) -> None:
    data = setup_member(clients(), core)
    raw = data["setup_url"].split("#token=")[1]
    first, second = clients(None), clients(None)
    headers = [csrf(first), csrf(second)]

    def consume(pair: tuple[TestClient, dict[str, str]]) -> int:
        client, hdr = pair
        return client.post(
            "/api/v1/auth/setup", headers=hdr, json={"setup_token": raw, "new_password": PASSWORD}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(consume, [(first, headers[0]), (second, headers[1])]))
    assert sorted(results) == [200, 400]


@pytest.mark.parametrize("role", ["admin", "manager", "agent", "viewer"])
def test_customer_role_matrix(core: Core, clients: Any, role: str) -> None:
    client = clients(role + "1")
    row = new_customer(clients())
    assert client.get(f"/api/v1/customers/{row['id']}").status_code == 200
    changed = mutate(client, f"/customers/{row['id']}", {"name": "Role matrix"}, "PATCH", 1)
    assert changed.status_code == (403 if role == "viewer" else 200)
    version = 1 if role == "viewer" else 2
    archived = mutate(
        client, f"/customers/{row['id']}/archive", {"reason": "Synthetic test"}, version=version
    )
    assert archived.status_code == (200 if role in {"admin", "manager"} else 403)
    assert mutate(client, "/teams", {"name": str(uuid4()), "member_ids": []}).status_code == (
        201 if role == "admin" else 403
    )


def test_access_change_transfers_ownership_and_revokes_sessions(core: Core, clients: Any) -> None:
    admin, actor = clients(), clients(None)
    data = setup_member(admin, core, "manager")
    raw = data["setup_url"].split("#token=")[1]
    assert (
        mutate(actor, "/auth/setup", {"setup_token": raw, "new_password": PASSWORD}).status_code
        == 200
    )
    member_id = data["member"]["id"]
    assert (
        mutate(
            actor,
            "/auth/login",
            {
                "workspace_slug": core.actors["admin1"]["workspace"],
                "audience": "staff",
                "email": data["member"]["email"],
                "password": PASSWORD,
            },
        ).status_code
        == 200
    )
    row = new_customer(admin, owner_member_id=member_id)
    workspace = admin.get("/api/v1/workspace").json()["data"]
    assert (
        mutate(
            admin,
            "/workspace",
            {"feedback_manager_member_id": member_id},
            "PATCH",
            workspace["version"],
        ).status_code
        == 200
    )
    path = f"/members/{member_id}"
    member = admin.get("/api/v1" + path).json()["data"]
    rejected = mutate(admin, path, {"role": "viewer"}, "PATCH", member["version"])
    assert rejected.status_code == 409 and rejected.json()["code"] == "replacement_required"
    assert (
        admin.get(f"/api/v1/customers/{row['id']}").json()["data"]["owner_member_id"] == member_id
    )
    replacement = str(core.actors["admin1"]["member"])
    assert (
        mutate(
            admin,
            path,
            {"role": "viewer", "replacement_member_id": replacement},
            "PATCH",
            member["version"],
        ).status_code
        == 200
    )
    assert actor.get("/api/v1/auth/me").status_code == 401
    assert (
        admin.get(f"/api/v1/customers/{row['id']}").json()["data"]["owner_member_id"] == replacement
    )
    assert (
        admin.get("/api/v1/workspace").json()["data"]["feedback_manager_member_id"] == replacement
    )
    engine = build_engine(core.app_url)
    with workspace_session(engine, core.workspaces[0]) as session:
        assert session.scalar(
            select(AuditEvent.id).where(
                AuditEvent.entity_id == UUID(row["id"]),
                AuditEvent.action == "customer.owner_reassigned",
            )
        )
    engine.dispose()


def test_operator_recovery_revokes_sessions_and_is_single_use(core: Core, clients: Any) -> None:
    data = setup_member(clients(), core)
    actor = clients(None)
    assert (
        mutate(
            actor,
            "/auth/setup",
            {
                "setup_token": data["setup_url"].split("#token=")[1],
                "new_password": PASSWORD,
            },
        ).status_code
        == 200
    )
    assert (
        mutate(
            actor,
            "/auth/login",
            {
                "workspace_slug": core.actors["admin1"]["workspace"],
                "audience": "staff",
                "email": data["member"]["email"],
                "password": PASSWORD,
            },
        ).status_code
        == 200
    )
    engine = build_engine(core.migration_url)
    with Session(engine) as session, session.begin():
        user = session.get(User, UUID(data["member"]["user_id"]))
        assert user
        url = issue_setup(session, user, "recovery")
    anonymous = clients(None)
    payload = {"setup_token": url.split("#token=")[1], "new_password": "Recovery-password-99"}
    assert mutate(anonymous, "/auth/setup", payload).status_code == 200
    assert mutate(anonymous, "/auth/setup", payload).status_code == 400
    assert actor.get("/api/v1/auth/me").status_code == 401
    engine.dispose()


def test_pending_portal_binding_requires_account_acceptance(core: Core, clients: Any) -> None:
    admin, portal = clients(), clients(None)
    existing = core.actors["manager2"]
    row = new_customer(admin)
    created = mutate(
        admin,
        "/contacts",
        {
            "customer_id": row["id"],
            "name": "Pending existing account",
            "email": existing["email"],
        },
    ).json()["data"]
    provisioned = mutate(admin, f"/contacts/{created['id']}/portal-access", version=1)
    assert provisioned.status_code == 200
    assert (
        mutate(
            admin, f"/contacts/{created['id']}/portal-access", {"active": True}, "PATCH", 2
        ).status_code
        == 409
    )
    engine = build_engine(core.app_url)
    with pytest.raises(DBAPIError), workspace_session(engine, core.workspaces[0]) as session:
        session.execute(
            update(PortalBinding)
            .where(PortalBinding.contact_id == UUID(created["id"]))
            .values(active=True)
        )
    assert (
        mutate(
            portal,
            "/auth/setup",
            {
                "setup_token": provisioned.json()["data"]["setup_url"].split("#token=")[1],
                "current_password": PASSWORD,
            },
        ).status_code
        == 200
    )
    assert (
        mutate(
            portal,
            "/auth/login",
            {
                "workspace_slug": core.actors["admin1"]["workspace"],
                "audience": "portal",
                "email": existing["email"],
                "password": PASSWORD,
            },
        ).status_code
        == 200
    )
    assert portal.get("/api/v1/auth/me").json()["data"]["contact_id"] == created["id"]
    assert admin.get(f"/api/v1/contacts/{created['id']}").json()["data"]["portal_enabled"] is True
    engine.dispose()


def test_concurrent_password_changes_cannot_leave_sessions_valid(core: Core, clients: Any) -> None:
    data = setup_member(clients(), core)
    first, second = clients(None), clients(None)
    assert (
        mutate(
            first,
            "/auth/setup",
            {
                "setup_token": data["setup_url"].split("#token=")[1],
                "new_password": PASSWORD,
            },
        ).status_code
        == 200
    )
    for client in (first, second):
        assert (
            mutate(
                client,
                "/auth/login",
                {
                    "workspace_slug": core.actors["admin1"]["workspace"],
                    "audience": "staff",
                    "email": data["member"]["email"],
                    "password": PASSWORD,
                },
            ).status_code
            == 200
        )
    headers = [csrf(first), csrf(second)]

    def change(pair: tuple[TestClient, dict[str, str]]) -> int:
        client, hdr = pair
        return client.post(
            "/api/v1/auth/password",
            headers=hdr,
            json={
                "current_password": PASSWORD,
                "new_password": "Concurrent-password-77",
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(change, [(first, headers[0]), (second, headers[1])]))
    assert sorted(results) == [200, 401]
    assert all(client.get("/api/v1/auth/me").status_code == 401 for client in (first, second))


def test_login_rate_limit_is_persisted(core: Core, clients: Any) -> None:
    email = f"unknown-{uuid4()}@example.com"
    body = {
        "workspace_slug": core.actors["admin1"]["workspace"],
        "audience": "staff",
        "email": email,
        "password": "wrong-password",
    }
    # Use a separate request IP so this attack fixture cannot lock legitimate fixture clients.
    with TestClient(
        create_app(), base_url="https://testserver", client=("198.51.100.44", 50000)
    ) as attack:
        attack.app.state.engine = build_engine(core.app_url)
        for _ in range(5):
            assert mutate(attack, "/auth/login", body).status_code == 401
        limited = mutate(attack, "/auth/login", body)
        assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0
