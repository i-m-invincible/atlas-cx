from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from test_m1_integration import Core, csrf, mutate, new_customer
from test_m1_integration import clients as clients
from test_m1_integration import core as core
from test_m2_integration import action, command, create_case, resolve, triage

from app.modules.customers.import_models import CustomerImport
from app.modules.followups.models import Feedback, Task
from app.modules.workspace.case_config_models import CaseConfig
from app.platform.database import build_engine, workspace_session

pytestmark = pytest.mark.integration


def stage(client: TestClient, data: str) -> Any:
    return client.post(
        "/api/v1/customer-imports/validate",
        headers=csrf(client),
        files={"file": ("customers.csv", data.encode(), "text/csv")},
    )


def test_second_preset_pins_old_rules_and_routes_new_cases(core: Core, clients: Any) -> None:
    admin, portal = clients("admin2"), clients("portala2")
    old = create_case(portal, core, True)
    team = mutate(
        admin,
        "/teams",
        {"name": "Appointments", "member_ids": [str(core.actors["admin2"]["member"])]},
    )
    assert team.status_code == 201, team.text
    team_id = team.json()["data"]["id"]
    presets = admin.get("/api/v1/case-presets").json()["data"]
    definition = next(row["definition"] for row in presets if row["key"] == "service_business")
    definition["categories"][0]["default_team_id"] = team_id
    definition["fields"][1]["required_on_create"] = True
    definition["fields"].append(
        {
            "key": "private_ref",
            "label": "Private reference",
            "type": "string",
            "required_on_create": True,
            "default": "internal-only",
        }
    )
    assert mutate(clients("manager2"), "/case-configs", definition).status_code == 403
    created = mutate(admin, "/case-configs", definition)
    assert created.status_code == 201, created.text
    draft = created.json()["data"]
    assert clients("agent2").get(f"/api/v1/case-configs/{draft['id']}").status_code == 404
    path = f"/case-configs/{draft['id']}/publish"
    replay_key = uuid4().hex
    assert command(admin, path, None, key=replay_key).status_code == 428
    assert command(admin, path, None, draft["version"], key=replay_key).status_code == 200
    assert command(admin, path, None, draft["version"], key=replay_key).status_code == 200
    assert (
        mutate(
            admin, f"/case-configs/{draft['id']}", definition, "PATCH", draft["version"] + 1
        ).status_code
        == 409
    )
    engine = build_engine(core.app_url)
    with pytest.raises(DBAPIError), workspace_session(engine, core.workspaces[1]) as session:
        session.execute(
            update(CaseConfig).where(CaseConfig.id == UUID(draft["id"])).values(number=999)
        )
    engine.dispose()
    active = portal.get("/api/v1/portal/config").json()["data"]
    assert [field["key"] for field in active["fields"]] == ["service_ref", "appointment_date"]
    assert "internal-only" not in str(active)
    input_data = {
        "category_key": "appointment",
        "subject": "Reschedule",
        "description": "A synthetic appointment",
    }
    assert command(portal, "/portal/cases", input_data).status_code == 422
    input_data["custom_values"] = {"appointment_date": "2026-11-09"}
    created_case = command(portal, "/portal/cases", input_data)
    assert created_case.status_code == 201, created_case.text
    case = created_case.json()["data"]
    assert case["custom_values"] == {"service_ref": None, "appointment_date": "2026-11-09"}
    staff = admin.get(f"/api/v1/cases/{case['id']}").json()["data"]
    assert staff["config_version_id"] == draft["id"] and staff["team"]["id"] == team_id
    assert staff["custom_values"]["private_ref"] == "internal-only"
    assert (
        portal.get(f"/api/v1/portal/cases/{old['id']}").json()["data"]["category_label"] == "Access"
    )
    prior = admin.get(f"/api/v1/cases/{old['id']}").json()["data"]
    assert prior["config_version_id"] != draft["id"]
    assert prior["state"] == "new"
    opened = action(admin, staff, "triage", assignee_member_id=str(core.actors["admin2"]["member"]))
    assert resolve(admin, opened)["state"] == "resolved"
    assert clients().get(f"/api/v1/cases/{case['id']}").status_code == 404


def test_publication_rejects_foreign_team_and_invalid_required_default(
    core: Core, clients: Any
) -> None:
    admin, other = clients(), clients("admin2")
    definition = admin.get("/api/v1/case-presets").json()["data"][0]["definition"]
    team = mutate(other, "/teams", {"name": "Other routing", "member_ids": []}).json()["data"]
    definition["categories"][0]["default_team_id"] = team["id"]
    draft = mutate(admin, "/case-configs", definition).json()["data"]
    path = f"/case-configs/{draft['id']}"
    assert command(admin, path + "/publish", None, 1).json()["code"] == "invalid_routing_team"
    definition["categories"][0]["default_team_id"] = None
    definition["fields"][0].update(
        portal_visible=False, portal_editable_on_create=False, required_on_create=True
    )
    updated = mutate(admin, path, definition, "PATCH", 1)
    assert updated.status_code == 200, updated.text
    assert command(admin, path + "/publish", None, 2).json()["code"] == "invalid_field"


def test_task_lifecycle_role_constraints_and_audit(core: Core, clients: Any) -> None:
    admin, agent, viewer = clients(), clients("agent1"), clients("viewer1")
    customer = new_customer(admin)
    body = {
        "customer_id": customer["id"],
        "title": "Synthetic follow-up",
        "assignee_member_id": str(core.actors["agent1"]["member"]),
        "due_at": "2020-01-01T00:00:00Z",
    }
    assert command(viewer, "/tasks", body).status_code == 403
    key = uuid4().hex
    first = command(agent, "/tasks", body, key=key)
    assert first.status_code == 201, first.text
    task = first.json()["data"]
    assert command(agent, "/tasks", body, key=key).json()["data"]["id"] == task["id"]
    path = f"/tasks/{task['id']}"
    assert viewer.get("/api/v1" + path).status_code == 200
    assert clients("admin2").get("/api/v1" + path).status_code == 404
    assert clients("portala1").get("/api/v1" + path).status_code == 403
    assert mutate(viewer, path, {"state": "cancelled"}, "PATCH", 1).status_code == 403
    assert mutate(agent, path, {"state": "completed"}, "PATCH", 1).status_code == 422
    assert (
        mutate(
            admin, f"/customers/{customer['id']}/archive", {"reason": "Test"}, version=1
        ).status_code
        == 409
    )
    overdue = admin.get(f"/api/v1/tasks?overdue=true&customer_id={customer['id']}").json()["data"]
    assert [row["id"] for row in overdue] == [task["id"]]
    completed = mutate(
        agent, path, {"state": "completed", "completion_note": "Checked the request."}, "PATCH", 1
    )
    assert completed.status_code == 200, completed.text
    done = completed.json()["data"]
    assert done["completed_by_member_id"] == str(core.actors["agent1"]["member"])
    assert done["completed_at"] and not done["overdue"]
    assert mutate(agent, path, {"state": "open"}, "PATCH", 1).status_code == 409
    reopened = mutate(agent, path, {"state": "open"}, "PATCH", 2).json()["data"]
    assert reopened["completed_at"] is None and reopened["overdue"]
    history = viewer.get("/api/v1" + path + "/history").json()["data"]
    assert [item["action"] for item in history] == [
        "task.reopened",
        "task.completed",
        "task.created",
    ]


def test_feedback_race_is_private_and_creates_exactly_one_task(core: Core, clients: Any) -> None:
    admin, portal, second = clients(), clients("portala1"), clients("portala1")
    other = clients("portalb1")
    case = resolve(admin, triage(admin, core, create_case(portal, core, True)))
    path = f"/portal/cases/{case['id']}/cycles/1/feedback"
    payload = {"rating": 2, "comment": "Synthetic private concern"}
    assert command(other, path, payload, case["version"]).status_code == 404
    assert command(admin, path, payload, case["version"]).status_code == 403
    assert command(portal, path, payload).status_code == 428
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result()
            for future in (
                executor.submit(command, portal, path, payload, case["version"]),
                executor.submit(command, second, path, payload, case["version"]),
            )
        ]
    assert sorted(response.status_code for response in results) == [201, 409]
    saved = next(response.json()["data"] for response in results if response.status_code == 201)
    assert set(saved) == {"id", "cycle_number", "rating", "comment", "created_at"}
    staff = admin.get(f"/api/v1/feedback?case_id={case['id']}").json()["data"]
    tasks = admin.get(f"/api/v1/tasks?case_id={case['id']}").json()["data"]
    assert len(staff) == len(tasks) == 1
    assert staff[0]["task_id"] == tasks[0]["id"] and tasks[0]["feedback_id"] == saved["id"]
    assert tasks[0]["assignee"]["id"] == str(core.actors["admin1"]["member"])
    assert datetime.fromisoformat(tasks[0]["due_at"]) - datetime.fromisoformat(
        saved["created_at"]
    ) == timedelta(hours=48)
    assert "private concern" not in tasks[0]["description"]
    assert other.get(f"/api/v1/portal/cases/{case['id']}/feedback").status_code == 404
    assert portal.get(f"/api/v1/portal/cases/{case['id']}").json()["data"]["can_rate"] is False
    engine = build_engine(core.app_url)
    actor = core.actors["portalb1"]
    with workspace_session(
        engine, core.workspaces[0], "portal", actor["user"], actor["contact"]
    ) as session:
        assert session.scalar(select(Feedback.id)) is None
        assert session.scalar(select(Task.id)) is None
    with pytest.raises(DBAPIError), workspace_session(engine, core.workspaces[0]) as session:
        session.execute(update(Feedback).where(Feedback.id == UUID(saved["id"])).values(rating=5))
    engine.dispose()


def test_feedback_replays_after_closure_and_high_rating_has_no_task(
    core: Core, clients: Any
) -> None:
    admin, portal = clients(), clients("portala1")
    case = resolve(admin, triage(admin, core, create_case(portal, core, True)))
    path = f"/portal/cases/{case['id']}/cycles/1/feedback"
    key = uuid4().hex
    response = command(portal, path, {"rating": 5}, case["version"], key)
    assert response.status_code == 201, response.text
    action(admin, case | {"version": case["version"] + 1}, "close", reason="Confirmed")
    replay = command(portal, path, {"rating": 5}, case["version"], key)
    assert replay.status_code == 201 and replay.json()["data"] == response.json()["data"]
    assert command(portal, path, {"rating": 4}, case["version"], key).status_code == 409
    assert admin.get(f"/api/v1/tasks?case_id={case['id']}").json()["data"] == []


def test_csv_preview_and_atomic_commit_preserve_optional_cells(core: Core, clients: Any) -> None:
    admin, manager = clients(), clients("manager1")
    external = uuid4().hex
    new_id = uuid4().hex
    existing = new_customer(admin, external_id=external, tags=["keep"], lifecycle="prospect")
    data = (
        "external_id,name,kind,lifecycle,tags,activity_expected\n"
        f"{external},Renamed,business,,,\n{new_id},New buyer,person,active,one;two,true\n"
    )
    assert stage(clients("agent1"), data).status_code == 403
    validated = stage(manager, data)
    assert validated.status_code == 201, validated.text
    row = validated.json()["data"]
    path = f"/customer-imports/{row['id']}"
    assert [item["action"] for item in row["rows"]] == ["update", "create"]
    assert (
        admin.get(f"/api/v1/customers/{existing['id']}").json()["data"]["name"] == existing["name"]
    )
    assert clients("admin2").get("/api/v1" + path).status_code == 404
    key = uuid4().hex
    assert command(admin, path + "/commit", None, key=key).status_code == 428
    committed = command(admin, path + "/commit", None, 1, key)
    assert committed.status_code == 200, committed.text
    result = committed.json()["data"]
    assert result["status"] == "committed"
    assert command(admin, path + "/commit", None, 1, key).json()["data"] == result
    assert command(admin, path + "/commit", None, 2).status_code == 409
    changed = admin.get(f"/api/v1/customers/{existing['id']}").json()["data"]
    assert (
        changed["name"] == "Renamed"
        and changed["tags"] == ["keep"]
        and changed["lifecycle"] == "prospect"
    )
    assert result["rows"][1]["customer_id"]


def test_csv_reports_duplicate_foreign_owner_and_leaves_no_partial_rows(
    core: Core, clients: Any
) -> None:
    admin = clients()
    external, valid = uuid4().hex, uuid4().hex
    outsider = core.actors["agent2"]["email"]
    preview = stage(
        admin,
        f"external_id,name,kind,owner_email\n{external},One,business,{outsider}\n{external},Two,unknown,\n{valid},Three,business,\n",
    )
    assert preview.status_code == 201, preview.text
    data = preview.json()["data"]
    assert [row["action"] for row in data["rows"]] == ["error", "error", "create"]
    assert {item["field"] for item in data["rows"][0]["errors"]} == {"external_id", "owner_email"}
    assert command(admin, f"/customer-imports/{data['id']}/commit", None, 1).status_code == 409
    assert not any(
        row["external_id"] == valid
        for row in admin.get("/api/v1/customers?limit=100").json()["data"]
    )


def test_csv_stale_preview_fails_before_applying_any_row(core: Core, clients: Any) -> None:
    admin = clients()
    external, first = uuid4().hex, uuid4().hex
    original = new_customer(admin, external_id=external)
    preview = stage(
        admin,
        "external_id,name,kind\n"
        f"{first},Should not exist,business\n{external},Stale name,business\n",
    ).json()["data"]
    assert (
        mutate(
            admin, f"/customers/{original['id']}", {"name": "Edited after preview"}, "PATCH", 1
        ).status_code
        == 200
    )
    path = f"/customer-imports/{preview['id']}"
    conflict = command(admin, path + "/commit", None, 1)
    assert conflict.status_code == 409 and conflict.json()["code"] == "import_changed"
    assert admin.get("/api/v1" + path).json()["data"]["status"] == "failed"
    assert not any(
        row["external_id"] == first
        for row in admin.get("/api/v1/customers?limit=100").json()["data"]
    )


def test_feedback_uses_customer_owner_then_manager_and_transfers_open_tasks(
    core: Core,
    clients: Any,
) -> None:
    admin, portal = clients(), clients("portala1")
    actor = core.actors["agent1"]["member"]
    customer_id = core.records["customer1"]
    customer = admin.get(f"/api/v1/customers/{customer_id}").json()["data"]
    owner = str(core.actors["manager1"]["member"])
    changed = mutate(
        admin, f"/customers/{customer_id}", {"owner_member_id": owner}, "PATCH", customer["version"]
    ).json()["data"]
    cases = [
        resolve(
            admin,
            action(admin, create_case(portal, core, True), "triage", assignee_member_id=str(actor)),
        )
        for _ in range(2)
    ]
    assigned = command(
        admin,
        "/tasks",
        {
            "customer_id": str(customer_id),
            "title": "Synthetic active work",
            "assignee_member_id": str(actor),
            "due_at": "2030-01-01T00:00:00Z",
        },
    ).json()["data"]
    replacement = str(core.actors["admin1"]["member"])
    response = mutate(
        admin,
        f"/members/{actor}",
        {
            "active": False,
            "replacement_member_id": replacement,
        },
        "PATCH",
        1,
    )
    assert response.status_code == 200, response.text
    assert (
        admin.get(f"/api/v1/tasks/{assigned['id']}").json()["data"]["assignee"]["id"] == replacement
    )
    for case, expected in zip(cases, (owner, replacement), strict=True):
        result = command(
            portal, f"/portal/cases/{case['id']}/cycles/1/feedback", {"rating": 1}, case["version"]
        )
        assert result.status_code == 201, result.text
        tasks = admin.get(f"/api/v1/tasks?case_id={case['id']}").json()["data"]
        assert tasks[0]["assignee"]["id"] == expected
        if expected == owner:
            assert (
                mutate(
                    admin,
                    f"/customers/{customer_id}",
                    {"owner_member_id": None},
                    "PATCH",
                    changed["version"],
                ).status_code
                == 200
            )


def test_expired_import_is_unavailable_and_staging_is_cleared(core: Core, clients: Any) -> None:
    admin = clients()
    external = uuid4().hex
    preview = stage(admin, f"external_id,name,kind\n{external},Expired,business\n").json()["data"]
    identifier = UUID(preview["id"])
    migration = build_engine(core.migration_url)
    with workspace_session(migration, core.workspaces[0]) as session:
        session.execute(
            update(CustomerImport)
            .where(CustomerImport.id == identifier)
            .values(expires_at=datetime(2020, 1, 1, tzinfo=UTC))
        )
    path = f"/customer-imports/{identifier}"
    response = command(admin, path + "/commit", None, 1)
    assert response.status_code == 409 and response.json()["code"] == "import_expired"
    with workspace_session(migration, core.workspaces[0]) as session:
        row = session.get(CustomerImport, identifier)
        assert row and row.status == "expired" and row.create_count == 1
        assert row.normalized_rows_json == row.row_results_json == []
    migration.dispose()
