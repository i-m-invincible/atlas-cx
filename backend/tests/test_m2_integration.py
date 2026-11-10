from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from test_m1_integration import (
    Core,
    csrf,
    mutate,
    new_customer,
)  # noqa: F401 -- shared real-role fixtures; pytest registers imported fixtures.
from test_m1_integration import clients as clients
from test_m1_integration import core as core

from app.modules.cases import repository as case_repository
from app.modules.cases import service as case_service
from app.modules.cases.models import Case, CaseCycle, CaseTransition, Message
from app.modules.workspace.case_config_models import CaseConfig
from app.platform.database import build_engine, workspace_session
from app.platform.idempotency import IdempotencyRecord

pytestmark = pytest.mark.integration


def command(
    client: TestClient,
    path: str,
    body: object,
    version: int | None = None,
    key: str | None = None,
    method: str = "POST",
) -> Any:
    headers = csrf(client)
    headers["Idempotency-Key"] = key or str(uuid4())
    if version is not None:
        headers["If-Match"] = f'"{version}"'
    return client.request(method, "/api/v1" + path, headers=headers, json=body)


def create_case(
    client: TestClient, core: Core, portal: bool = False, **changes: Any
) -> dict[str, Any]:
    body = {
        "subject": f"Synthetic request {uuid4()}",
        "description": "Synthetic initial request",
        "category_key": "access",
        **changes,
    }
    if not portal:
        body = {
            "customer_id": str(core.records["customer1"]),
            "requester_contact_id": str(core.actors["portala1"]["contact"]),
            **body,
        }
    response = command(client, "/portal/cases" if portal else "/cases", body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def action(client: TestClient, row: dict[str, Any], name: str, **fields: Any) -> dict[str, Any]:
    response = command(
        client, f"/cases/{row['id']}/transitions", {"action": name, **fields}, row["version"]
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["case"]


def triage(client: TestClient, core: Core, row: dict[str, Any]) -> dict[str, Any]:
    return action(client, row, "triage", assignee_member_id=str(core.actors["admin1"]["member"]))


def resolve(client: TestClient, row: dict[str, Any]) -> dict[str, Any]:
    return action(
        client,
        row,
        "resolve",
        resolution_summary="Synthetic public resolution",
        resolution_code="fixed",
    )


def test_creation_is_atomic_pinned_and_numbered(core: Core, clients: Any) -> None:
    admin = clients()
    first, second = create_case(admin, core), create_case(admin, core)
    assert second["number"] == first["number"] + 1
    assert first["state"] == "new" and first["assignee"] is None
    assert first["first_response_at"] is None
    assert first["first_response_status"]["target_seconds"] == 28800
    assert first["current_cycle"]["target_seconds"] == 172800
    config = admin.get(f"/api/v1/case-configs/{first['config_version_id']}")
    assert config.status_code == 200 and config.headers["ETag"] == '"1"'
    engine = build_engine(core.app_url)
    with workspace_session(engine, core.workspaces[0]) as session:
        identifier = UUID(first["id"])
        assert (
            session.scalar(
                select(func.count()).select_from(CaseCycle).where(CaseCycle.case_id == identifier)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count()).select_from(Message).where(Message.case_id == identifier)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(CaseTransition)
                .where(CaseTransition.case_id == identifier)
            )
            == 1
        )
    engine.dispose()


def test_portal_creation_derives_identity_and_omits_internal_context(
    core: Core, clients: Any
) -> None:
    portal, admin = clients("portala1"), clients()
    row = create_case(portal, core, True)
    staff = admin.get(f"/api/v1/cases/{row['id']}").json()["data"]
    assert staff["customer"]["id"] == str(core.records["customer1"])
    assert staff["requester"]["id"] == str(core.actors["portala1"]["contact"])
    forbidden = {
        "assignee",
        "team",
        "priority",
        "source",
        "target_status",
        "cycles",
        "customer",
        "requester",
        "updated_at",
        "last_message_at",
    }
    assert not forbidden.intersection(row)
    assert row["can_reply"] and not row["can_rate"]
    configuration = portal.get("/api/v1/portal/config").json()["data"]
    assert set(configuration) == {"categories", "state_labels", "fields"}
    assert "default_team_id" not in str(configuration) and "priorities" not in str(configuration)
    assert (
        command(
            portal,
            "/portal/cases",
            {
                "category_key": "access",
                "subject": "Forged",
                "description": "Text",
                "customer_id": str(core.records["customer2"]),
            },
        ).status_code
        == 422
    )


def test_public_reply_opens_case_but_note_is_not_a_response(core: Core, clients: Any) -> None:
    admin, portal = clients(), clients("portala1")
    row = create_case(portal, core, True)
    note = command(
        admin,
        f"/cases/{row['id']}/messages",
        {"body": "Sensitive internal note", "visibility": "internal"},
        1,
    )
    assert note.status_code == 200
    detail = admin.get(f"/api/v1/cases/{row['id']}").json()["data"]
    assert detail["state"] == "new" and detail["first_response_at"] is None
    reply = command(
        admin, f"/cases/{row['id']}/messages", {"body": "Public help", "visibility": "public"}, 2
    )
    assert reply.status_code == 200
    detail = admin.get(f"/api/v1/cases/{row['id']}").json()["data"]
    assert detail["state"] == "open" and detail["assignee"]["id"] == str(
        core.actors["admin1"]["member"]
    )
    first_response = detail["first_response_at"]
    assert (
        command(
            admin, f"/cases/{row['id']}/messages", {"body": "Another public reply"}, 3
        ).status_code
        == 200
    )
    assert (
        admin.get(f"/api/v1/cases/{row['id']}").json()["data"]["first_response_at"]
        == first_response
    )
    public = portal.get(f"/api/v1/portal/cases/{row['id']}/messages").json()
    assert [item["body"] for item in public["data"]] == [
        "Synthetic initial request",
        "Public help",
        "Another public reply",
    ]
    assert "Sensitive internal note" not in str(public)
    assert all(item["author_display"] in {"You", "Support team"} for item in public["data"])
    assert portal.get("/api/v1/portal/cases?q=Sensitive%20internal%20note").json()["data"] == []


@pytest.mark.parametrize("actor", ["portalb1", "portala2"])
def test_other_contacts_cannot_read_reply_or_reopen(core: Core, clients: Any, actor: str) -> None:
    owner, other = clients("portala1"), clients(actor)
    row = create_case(owner, core, True)
    base = f"/portal/cases/{row['id']}"
    assert other.get("/api/v1" + base).status_code == 404
    assert other.get("/api/v1" + base + "/messages").status_code == 404
    assert command(other, base + "/messages", {"body": "Forbidden"}, 1).status_code == 404
    assert command(other, base + "/reopen", {"message": "Forbidden"}, 1).status_code == 404
    assert all(item["id"] != row["id"] for item in other.get("/api/v1/portal/cases").json()["data"])
    assert (
        command(
            other,
            "/portal/cases",
            {
                "subject": "Related",
                "description": "Forbidden relation",
                "category_key": "access",
                "related_case_id": row["id"],
            },
        ).status_code
        == 404
    )


@pytest.mark.parametrize("actor", ["admin2", "agent2", "viewer2"])
def test_other_workspace_staff_object_endpoints_fail_closed(
    core: Core, clients: Any, actor: str
) -> None:
    row = create_case(clients(), core)
    other = clients(actor)
    base = f"/cases/{row['id']}"
    for suffix in ("", "/messages", "/history"):
        assert other.get("/api/v1" + base + suffix).status_code == 404
    assert command(other, base, {"priority": "high"}, 1, method="PATCH").status_code == 404
    assert command(other, base + "/messages", {"body": "Forbidden"}, 1).status_code == 404
    assert command(other, base + "/transitions", {"action": "triage"}, 1).status_code == 404


def test_viewer_portal_and_anonymous_permissions(core: Core, clients: Any) -> None:
    row = create_case(clients(), core)
    viewer, portal, anonymous = clients("viewer1"), clients("portala1"), clients(None)
    assert viewer.get(f"/api/v1/cases/{row['id']}").status_code == 200
    assert (
        command(viewer, f"/cases/{row['id']}/messages", {"body": "Forbidden"}, 1).status_code == 403
    )
    assert (
        command(viewer, f"/cases/{row['id']}", {"priority": "high"}, 1, method="PATCH").status_code
        == 403
    )
    assert portal.get(f"/api/v1/cases/{row['id']}").status_code == 403
    assert clients().get("/api/v1/portal/cases").status_code == 403
    assert anonymous.get("/api/v1/cases").status_code == 401
    assert (
        command(
            portal,
            f"/portal/cases/{row['id']}/messages",
            {"body": "Secret", "visibility": "internal"},
            1,
        ).status_code
        == 422
    )


def test_real_portal_role_sees_only_own_public_rows(core: Core, clients: Any) -> None:
    owner, admin = clients("portala1"), clients()
    row = create_case(owner, core, True)
    other = create_case(clients("portalb1"), core, True)
    assert (
        command(
            admin,
            f"/cases/{row['id']}/messages",
            {"body": "Internal secret", "visibility": "internal"},
            1,
        ).status_code
        == 200
    )
    actor = core.actors["portala1"]
    engine = build_engine(core.app_url)
    with workspace_session(
        engine, core.workspaces[0], "portal", actor["user"], actor["contact"]
    ) as session:
        assert session.scalar(text("SELECT current_user")) == "atlas_app"
        ids = set(session.scalars(select(Case.id)))
        assert UUID(row["id"]) in ids and UUID(other["id"]) not in ids
        bodies = list(session.scalars(select(Message.body)))
        assert "Internal secret" not in bodies
        assert session.scalars(select(CaseCycle.id)).all() == []
        assert session.scalars(select(CaseTransition.id)).all() == []
        assert session.scalars(select(CaseConfig.id)).all() == []
        assert session.scalars(select(IdempotencyRecord.id)).all() == []
        assert (
            session.execute(
                update(Case).where(Case.id == UUID(row["id"])).values(subject="forged")
            ).rowcount
            == 0
        )
    with (
        pytest.raises(DBAPIError),
        workspace_session(
            engine, core.workspaces[0], "portal", actor["user"], actor["contact"]
        ) as session,
    ):
        session.add(
            Message(
                workspace_id=core.workspaces[0],
                case_id=UUID(row["id"]),
                author_user_id=actor["user"],
                author_kind="staff",
                visibility="internal",
                message_kind="note",
                body="Forged",
                updated_case_version=3,
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
    engine.dispose()


def test_claim_is_atomic_under_two_agents(core: Core, clients: Any) -> None:
    row = create_case(clients("portala1"), core, True)
    first, second = clients("agent1"), clients("manager1")
    headers = [csrf(first), csrf(second)]

    def claim(index: int) -> Any:
        client, actor = (first, "agent1") if index == 0 else (second, "manager1")
        return client.post(
            f"/api/v1/cases/{row['id']}/transitions",
            headers={**headers[index], "If-Match": '"1"', "Idempotency-Key": str(uuid4())},
            json={"action": "triage", "assignee_member_id": str(core.actors[actor]["member"])},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, [0, 1]))
    assert sorted(response.status_code for response in results) == [200, 409]
    loser = next(response for response in results if response.status_code == 409)
    assert loser.json()["code"] == "version_conflict"
    detail = clients().get(f"/api/v1/cases/{row['id']}").json()["data"]
    assert detail["state"] == "open" and detail["version"] == 2


def test_complete_clock_cycle_and_portal_reopening(
    core: Core, clients: Any, monkeypatch: Any
) -> None:
    instant = {"value": datetime(2026, 11, 8, 9, tzinfo=UTC)}
    monkeypatch.setattr(case_service, "now", lambda: instant["value"])
    monkeypatch.setattr(case_repository, "now", lambda: instant["value"])
    portal, admin = clients("portala1"), clients()
    row = create_case(portal, core, True)
    engine = build_engine(core.migration_url)
    with workspace_session(engine, core.workspaces[0]) as session:
        session.execute(
            update(Case).where(Case.id == UUID(row["id"])).values(resolution_target_seconds=7200)
        )
        session.execute(
            update(CaseCycle)
            .where(CaseCycle.case_id == UUID(row["id"]))
            .values(target_seconds=7200)
        )
    row = triage(admin, core, row)
    instant["value"] = datetime(2026, 11, 8, 10, tzinfo=UTC)
    row = action(admin, row, "ask_customer", message="Please supply the reference.")
    assert row["target_status"]["status"] == "paused" and row["target_status"]["due_at"] is None
    assert row["target_status"]["remaining_seconds"] == 3600
    instant["value"] = datetime(2026, 11, 8, 12, tzinfo=UTC)
    replied = command(
        portal,
        f"/portal/cases/{row['id']}/messages",
        {"body": "Here is the reference."},
        row["version"],
    )
    assert replied.status_code == 200
    row = admin.get(f"/api/v1/cases/{row['id']}").json()["data"]
    assert row["state"] == "open" and row["current_cycle"]["paused_seconds"] == 7200
    instant["value"] = datetime(2026, 11, 8, 12, 45, tzinfo=UTC)
    row = resolve(admin, row)
    assert row["target_status"]["elapsed_seconds"] == 6300
    assert row["target_status"]["status"] == "met"
    first_response = row["first_response_at"]
    assert (
        command(
            portal, f"/portal/cases/{row['id']}/messages", {"body": "More help"}, row["version"]
        ).json()["code"]
        == "reopen_required"
    )
    instant["value"] = datetime(2026, 11, 8, 14, tzinfo=UTC)
    reopened = command(
        portal,
        f"/portal/cases/{row['id']}/reopen",
        {"message": "Still not working"},
        row["version"],
    )
    assert reopened.status_code == 200
    row = admin.get(f"/api/v1/cases/{row['id']}").json()["data"]
    assert row["current_cycle"]["cycle_number"] == 2
    assert (
        row["current_cycle"]["target_seconds"] == 7200
        and row["current_cycle"]["paused_seconds"] == 0
    )
    assert (
        row["cycles"][0]["paused_seconds"] == 7200 and row["cycles"][0]["resolved_at"] is not None
    )
    assert row["first_response_at"] == first_response
    assert row["target_status"]["elapsed_seconds"] == 0
    engine.dispose()


def test_direct_resolution_settles_running_pause(core: Core, clients: Any) -> None:
    admin = clients()
    row = triage(admin, core, create_case(admin, core))
    row = action(admin, row, "ask_customer", message="Please confirm.")
    row = resolve(admin, row)
    assert row["current_cycle"]["pause_started_at"] is None
    assert row["current_cycle"]["paused_seconds"] >= 0
    assert row["current_cycle"]["resolved_at"] is not None


@pytest.mark.parametrize(
    "state,action_name",
    [
        ("new", "resume"),
        ("new", "ask_customer"),
        ("open", "triage"),
        ("open", "reopen"),
        ("pending_customer", "ask_customer"),
        ("resolved", "resolve"),
        ("resolved", "triage"),
        ("closed", "reopen"),
        ("closed", "close"),
    ],
)
def test_invalid_transitions_leave_no_fragments(
    core: Core, clients: Any, state: str, action_name: str
) -> None:
    admin = clients()
    row = create_case(admin, core)
    if state != "new":
        row = triage(admin, core, row)
    if state == "pending_customer":
        row = action(admin, row, "ask_customer", message="Question")
    if state in {"resolved", "closed"}:
        row = resolve(admin, row)
    if state == "closed":
        row = action(admin, row, "close", reason="Administrative closure")
    payloads = {
        "triage": {"assignee_member_id": str(core.actors["admin1"]["member"])},
        "resume": {"reason": "Resume"},
        "ask_customer": {"message": "Question"},
        "resolve": {"resolution_summary": "Summary", "resolution_code": "fixed"},
        "reopen": {"reason": "Reopen"},
        "close": {"reason": "Close"},
    }
    before = admin.get(f"/api/v1/cases/{row['id']}/history").json()["data"]
    response = command(
        admin,
        f"/cases/{row['id']}/transitions",
        {"action": action_name, **payloads[action_name]},
        row["version"],
    )
    assert response.status_code == 409 and response.json()["code"] == "invalid_transition"
    after = admin.get(f"/api/v1/cases/{row['id']}").json()["data"]
    assert after["version"] == row["version"] and after["state"] == state
    assert admin.get(f"/api/v1/cases/{row['id']}/history").json()["data"] == before


def test_preconditions_validation_and_terminal_closed_cases(core: Core, clients: Any) -> None:
    admin, portal = clients(), clients("portala1")
    row = create_case(admin, core)
    assert (
        command(admin, f"/cases/{row['id']}", {"priority": "urgent"}, method="PATCH").status_code
        == 428
    )
    assert (
        command(admin, f"/cases/{row['id']}", {"state": "resolved"}, 1, method="PATCH").status_code
        == 422
    )
    assert (
        command(
            admin,
            f"/cases/{row['id']}/transitions",
            {"action": "resolve", "resolution_summary": "Summary", "resolution_code": "fixed"},
            1,
        ).status_code
        == 409
    )
    row = resolve(admin, triage(admin, core, row))
    assert (
        command(
            clients("agent1"),
            f"/cases/{row['id']}/transitions",
            {"action": "close", "reason": "No permission"},
            row["version"],
        ).status_code
        == 403
    )
    row = action(admin, row, "close", reason="Administrative closure")
    assert (
        command(
            admin, f"/cases/{row['id']}", {"priority": "low"}, row["version"], method="PATCH"
        ).status_code
        == 409
    )
    assert (
        command(
            admin,
            f"/cases/{row['id']}/messages",
            {"body": "Closed note", "visibility": "internal"},
            row["version"],
        ).status_code
        == 409
    )
    assert (
        command(
            portal, f"/portal/cases/{row['id']}/messages", {"body": "Closed reply"}, row["version"]
        ).status_code
        == 409
    )
    related = create_case(portal, core, True, related_case_id=row["id"])
    assert related["related_case_id"] == row["id"]


def test_idempotency_precedes_stale_version_and_never_duplicates(core: Core, clients: Any) -> None:
    portal, admin = clients("portala1"), clients()
    payload = {"subject": "Replay request", "description": "Once only", "category_key": "access"}
    key = str(uuid4())
    first = command(portal, "/portal/cases", payload, key=key)
    second = command(portal, "/portal/cases", payload, key=key)
    assert (
        first.status_code == second.status_code == 201
        and first.json()["data"]["id"] == second.json()["data"]["id"]
    )
    assert (
        command(portal, "/portal/cases", {**payload, "subject": "Different"}, key=key).json()[
            "code"
        ]
        == "idempotency_conflict"
    )
    row = first.json()["data"]
    key = str(uuid4())
    path = f"/cases/{row['id']}/messages"
    posted = command(admin, path, {"body": "Idempotent reply"}, 1, key)
    replayed = command(admin, path, {"body": "Idempotent reply"}, 1, key)
    assert (
        posted.status_code == replayed.status_code == 200
        and posted.json()["data"]["id"] == replayed.json()["data"]["id"]
    )
    assert admin.get(f"/api/v1/cases/{row['id']}").json()["data"]["version"] == 2
    key = str(uuid4())
    path = f"/cases/{row['id']}/transitions"
    payload = {
        "action": "resolve",
        "resolution_summary": "Idempotent resolution",
        "resolution_code": "answered",
    }
    resolved = command(admin, path, payload, 2, key)
    replayed = command(admin, path, payload, 2, key)
    assert resolved.status_code == replayed.status_code == 200
    assert resolved.json()["data"]["transition_id"] == replayed.json()["data"]["transition_id"]
    assert resolved.json()["data"]["message_id"] == replayed.json()["data"]["message_id"]
    messages = admin.get(f"/api/v1/cases/{row['id']}/messages").json()["data"]
    assert len(messages) == 3
    headers = csrf(portal)
    assert (
        portal.post(
            "/api/v1/portal/cases",
            headers=headers,
            json={"subject": "Missing key", "description": "Text", "category_key": "access"},
        ).status_code
        == 400
    )


def test_read_markers_are_explicit_monotonic_and_case_scoped(core: Core, clients: Any) -> None:
    admin, agent, portal = clients(), clients("agent1"), clients("portala1")
    row = create_case(portal, core, True)
    assert agent.get(f"/api/v1/cases/{row['id']}").json()["data"]["unread"]
    messages = agent.get(f"/api/v1/cases/{row['id']}/messages").json()["data"]
    assert agent.get(f"/api/v1/cases/{row['id']}").json()["data"]["unread"]
    sequence = messages[-1]["sequence"]
    marked = command(agent, f"/cases/{row['id']}/read-marker", {"last_read_sequence": sequence})
    assert marked.status_code == 200
    assert not agent.get(f"/api/v1/cases/{row['id']}").json()["data"]["unread"]
    assert (
        command(agent, f"/cases/{row['id']}/read-marker", {"last_read_sequence": 0}).json()["data"][
            "last_read_sequence"
        ]
        == sequence
    )
    other = create_case(admin, core)
    wrong = admin.get(f"/api/v1/cases/{other['id']}/messages").json()["data"][0]["sequence"]
    assert (
        command(agent, f"/cases/{row['id']}/read-marker", {"last_read_sequence": wrong}).status_code
        == 422
    )
    assert (
        command(admin, f"/cases/{row['id']}/messages", {"body": "Fresh response"}, 1).status_code
        == 200
    )
    assert agent.get(f"/api/v1/cases/{row['id']}").json()["data"]["unread"]


def test_filters_cursor_scope_and_message_sequence(core: Core, clients: Any) -> None:
    admin, portal = clients(), clients("portala1")
    marker = uuid4().hex
    for priority in ("low", "urgent", "high"):
        create_case(admin, core, subject=marker, priority=priority)
    path = f"/api/v1/cases?q={marker}&sort=priority&limit=1"
    page = admin.get(path).json()
    assert page["data"][0]["priority"] == "urgent"
    cursor = page["meta"]["next_cursor"]
    next_page = admin.get(path + "&cursor=" + cursor).json()
    assert next_page["data"][0]["priority"] == "high"
    assert admin.get(path + "&state=open&cursor=" + cursor).status_code == 400
    assert clients("admin2").get(path + "&cursor=" + cursor).status_code == 400
    assert portal.get(f"/api/v1/portal/cases?q={marker}&cursor={cursor}").status_code == 400
    row = page["data"][0]
    for version in (1, 2, 3):
        assert (
            command(
                admin,
                f"/cases/{row['id']}/messages",
                {"body": f"Ordered {version}", "visibility": "internal"},
                version,
            ).status_code
            == 200
        )
    first = admin.get(f"/api/v1/cases/{row['id']}/messages?limit=2").json()
    second = admin.get(
        f"/api/v1/cases/{row['id']}/messages?limit=2&cursor={first['meta']['next_cursor']}"
    ).json()
    sequence = [message["sequence"] for message in first["data"] + second["data"]]
    assert sequence == sorted(set(sequence)) and len(sequence) == 4


def test_database_constraints_and_append_only_grants(core: Core, clients: Any) -> None:
    row = create_case(clients(), core)
    identifier = UUID(row["id"])
    engine = build_engine(core.app_url)
    for operation in (
        update(Message).where(Message.case_id == identifier).values(body="Forged"),
        delete(Message).where(Message.case_id == identifier),
        update(CaseTransition).where(CaseTransition.case_id == identifier).values(reason="Forged"),
        update(CaseConfig)
        .where(CaseConfig.id == UUID(row["config_version_id"]))
        .values(definition_json={}),
        update(Case).where(Case.id == identifier).values(customer_id=core.records["customer2"]),
        update(CaseCycle).where(CaseCycle.case_id == identifier).values(paused_seconds=-1),
    ):
        with pytest.raises(DBAPIError), workspace_session(engine, core.workspaces[0]) as session:
            session.execute(operation)
    with pytest.raises(DBAPIError), workspace_session(engine, core.workspaces[0]) as session:
        session.add(
            CaseCycle(
                workspace_id=core.workspaces[0],
                case_id=identifier,
                cycle_number=2,
                opened_at=datetime.now(UTC),
                target_seconds=3600,
            )
        )
        session.flush()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id FROM cases")).all() == []
        assert connection.execute(text("SELECT id FROM messages")).all() == []
    engine.dispose()


def test_team_constraints_and_atomic_member_reassignment(core: Core, clients: Any) -> None:
    admin, agent, manager = clients(), clients("agent1"), clients("manager1")
    agent_id, manager_id = (
        str(core.actors["agent1"]["member"]),
        str(core.actors["manager1"]["member"]),
    )
    team = mutate(
        admin, "/teams", {"name": f"Case team {uuid4()}", "member_ids": [agent_id]}
    ).json()["data"]
    row = create_case(admin, core, team_id=team["id"])
    path = f"/cases/{row['id']}/transitions"
    assert (
        command(
            manager, path, {"action": "triage", "assignee_member_id": manager_id}, 1
        ).status_code
        == 422
    )
    claimed = command(agent, path, {"action": "triage", "assignee_member_id": agent_id}, 1)
    assert claimed.status_code == 200
    assert (
        command(
            admin,
            f"/cases/{row['id']}",
            {"assignee_member_id": str(core.actors["viewer1"]["member"])},
            2,
            method="PATCH",
        ).status_code
        == 422
    )
    assert mutate(admin, f"/teams/{team['id']}", {"member_ids": []}, "PATCH", 1).status_code == 409
    assert mutate(admin, f"/teams/{team['id']}", {"archived": True}, "PATCH", 1).status_code == 409
    member_path = f"/members/{agent_id}"
    member = admin.get("/api/v1" + member_path).json()["data"]
    assert (
        mutate(
            admin,
            member_path,
            {"active": False, "replacement_member_id": manager_id},
            "PATCH",
            member["version"],
        ).status_code
        == 409
    )
    assert agent.get("/api/v1/auth/me").status_code == 200
    assert (
        mutate(
            admin, f"/teams/{team['id']}", {"member_ids": [agent_id, manager_id]}, "PATCH", 1
        ).status_code
        == 200
    )
    deactivated = mutate(
        admin,
        member_path,
        {"active": False, "replacement_member_id": manager_id},
        "PATCH",
        member["version"],
    )
    assert deactivated.status_code == 200, deactivated.text
    try:
        assert agent.get("/api/v1/auth/me").status_code == 401
        transferred = admin.get(f"/api/v1/cases/{row['id']}").json()["data"]
        assert transferred["assignee"]["id"] == manager_id and transferred["version"] == 3
    finally:
        restored = mutate(
            admin, member_path, {"active": True}, "PATCH", deactivated.json()["data"]["version"]
        )
        assert restored.status_code == 200


def test_customer_archive_requires_no_active_cases(core: Core, clients: Any) -> None:
    admin = clients()
    customer = new_customer(admin)
    contact = mutate(
        admin,
        "/contacts",
        {
            "customer_id": customer["id"],
            "name": "Archive fixture",
            "email": f"archive-{uuid4()}@example.com",
        },
    ).json()["data"]
    payload = {
        "subject": "Archive and retry fixture",
        "description": "A retry must not create another case after archiving.",
        "category_key": "access",
        "customer_id": customer["id"],
        "requester_contact_id": contact["id"],
    }
    key = str(uuid4())
    created = command(admin, "/cases", payload, key=key)
    assert created.status_code == 201
    row = created.json()["data"]
    assert (
        mutate(
            admin, f"/customers/{customer['id']}/archive", {"reason": "Archive"}, version=1
        ).status_code
        == 409
    )
    assert (
        mutate(
            admin, f"/contacts/{contact['id']}/archive", {"reason": "Archive"}, version=1
        ).status_code
        == 409
    )
    resolve(admin, triage(admin, core, row))
    assert (
        mutate(
            admin,
            f"/customers/{customer['id']}/archive",
            {"reason": "Historical record"},
            version=1,
        ).status_code
        == 200
    )
    replay = command(admin, "/cases", payload, key=key)
    assert replay.status_code == 201 and replay.json()["data"]["id"] == row["id"]
    assert command(admin, "/cases", payload).status_code == 409
