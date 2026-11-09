# ruff: noqa: E501
import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_m1_integration import Core, mutate, new_customer
from test_m1_integration import clients as clients
from test_m1_integration import core as core

from app.modules.activities import service
from app.platform.config import get_settings
from app.platform.database import build_engine, workspace_session
from app.platform.protocol import now

pytestmark = pytest.mark.integration
BASE = "/api/v1"
INSTANT = datetime(2026, 6, 1, 12, tzinfo=UTC)


def test_ingestion_and_customer_timeline(core: Core, clients, monkeypatch) -> None:
    monkeypatch.setattr(service, "now", lambda: INSTANT)
    admin, peer, portal = clients(), clients("admin2"), clients("portala1")
    anonymous, concurrent = clients(None), clients(None)
    customer = new_customer(admin, external_id="m4-synthetic-product", activity_expected=True)
    foreign = new_customer(peer, external_id="m4-synthetic-foreign")
    customer_id = customer["id"]
    events = f"{BASE}/customers/{customer_id}/events"
    timeline = f"{BASE}/customers/{customer_id}/timeline"
    definition = mutate(
        admin,
        "/event-definitions",
        {
            "key": "feature_used",
            "label": "Synthetic feature used",
            "counts_as_activity": True,
            "allowed_properties": {
                "count": {"type": "integer"},
                "label": {"type": "string", "max_length": 8192},
            },
        },
    )
    assert definition.status_code == 201, definition.text
    definition_id = definition.json()["data"]["id"]
    issued = mutate(admin, "/api-credentials", {"name": "Synthetic ingestion"})
    assert issued.status_code == 201, issued.text if issued.status_code != 201 else ""
    key = issued.json()["data"]
    headers = {"Authorization": "Bearer " + key["secret"]}
    list_keys = admin.get(BASE + "/api-credentials").json()["data"]
    assert "secret" not in list_keys[0] and "token_hash" not in list_keys[0]
    assert clients("manager1").get(BASE + "/api-credentials").status_code == 403
    assert peer.get(f"{BASE}/api-credentials/{key['id']}").status_code == 404

    def payload(identifier: str, stamp: datetime = INSTANT, **changes):
        return {
            "external_event_id": identifier,
            "customer_external_id": customer["external_id"],
            "occurred_at": stamp.isoformat(),
            "event_name": "feature_used",
            "properties": {"count": 1, "label": "Synthetic activity"},
            **changes,
        }

    def send(*items, client=anonymous):
        return client.post(BASE + "/events/batch", headers=headers, json={"events": items})

    assert (
        anonymous.post(BASE + "/events/batch", json={"events": [payload("auth")]}).status_code
        == 401
    )
    assert send({**payload("unknown"), "event_name": "unknown"}).status_code == 422
    assert (
        send({**payload("foreign"), "customer_external_id": foreign["external_id"]}).status_code
        == 422
    )
    assert send({**payload("scalar"), "properties": {"count": True}}).status_code == 422
    assert send({**payload("unknown-field"), "properties": {"x": 1}}).status_code == 422
    assert (
        send({**payload("properties-size"), "properties": {"label": "é" * 4096}}).status_code == 413
    )
    assert (
        anonymous.post(
            BASE + "/events/batch",
            headers={**headers, "Content-Type": "application/json"},
            content=b" " * (1024 * 1024 + 1),
        ).status_code
        == 413
    )
    older = payload("old", INSTANT - timedelta(days=90))
    future = payload("future", INSTANT + timedelta(minutes=5))
    assert send(payload("too-old", INSTANT - timedelta(days=90, microseconds=1))).status_code == 422
    assert (
        send(payload("too-new", INSTANT + timedelta(minutes=5, microseconds=1))).status_code == 422
    )
    first = send(future, older, older)
    assert first.status_code == 200, first.text
    data = first.json()["data"]
    assert (data["inserted_count"], data["duplicate_count"]) == (2, 1)
    assert data["ids"][1] == data["ids"][2]
    assert send(payload("atomic"), {**older, "properties": {"count": 2}}).status_code == 409
    with ThreadPoolExecutor(max_workers=2) as executor:
        submissions = [
            executor.submit(send, payload("race"), client=client)
            for client in (anonymous, concurrent)
        ]
    outcomes = [item.result() for item in submissions]
    assert [response.status_code for response in outcomes] == [200, 200]
    assert sorted(response.json()["data"]["inserted_count"] for response in outcomes) == [0, 1]
    assert outcomes[0].json()["data"]["ids"] == outcomes[1].json()["data"]["ids"]

    updated = mutate(
        admin,
        f"/event-definitions/{definition_id}",
        {"enabled": False, "counts_as_activity": False},
        method="PATCH",
        version=1,
    )
    assert updated.status_code == 200
    assert send(payload("disabled")).status_code == 422
    assert send(older).json()["data"]["duplicate_count"] == 1
    assert (
        send({**older, "occurred_at": "2026-03-03T08:00:00-04:00"}).json()["data"][
            "duplicate_count"
        ]
        == 1
    )
    page = admin.get(events, params={"limit": 2, "event_name": "feature_used"})
    assert page.status_code == 200, page.text
    assert [row["external_event_id"] for row in page.json()["data"]] == ["future", "race"]
    cursor = page.json()["meta"]["next_cursor"]
    assert admin.get(events, params={"cursor": cursor}).status_code == 400
    last = admin.get(events, params={"event_name": "feature_used", "cursor": cursor}).json()["data"]
    assert [row["external_event_id"] for row in last] == ["old"]
    assert last[0]["counts_as_activity"] is True
    assert admin.get(f"{events}/{last[0]['id']}").json()["data"]["properties"]["count"] == 1
    customer_view = admin.get(f"{BASE}/customers/{customer_id}").json()["data"]
    assert customer_view["last_event_received_at"] is not None
    assert customer_view["last_meaningful_activity_at"] == future["occurred_at"].replace(
        "+00:00", "Z"
    )
    rows = admin.get(timeline, params={"kinds": "event"}).json()["data"]
    assert [row["reference_id"] for row in rows] == [
        data["ids"][0],
        outcomes[0].json()["data"]["ids"][0],
        data["ids"][1],
    ]
    assert peer.get(events).status_code == 404
    assert peer.get(timeline).status_code == 404
    assert portal.get(events).status_code == 403
    assert portal.get(timeline).status_code == 403

    engine = build_engine(core.app_url)
    try:
        with workspace_session(engine, core.workspaces[0]) as db:
            assert db.scalar(text("SELECT current_user")) == "atlas_app"
            assert db.scalar(text("SELECT count(*) FROM customer_events")) == 3
        for workspace, audience in ((core.workspaces[1], "staff"), (core.workspaces[0], "portal")):
            with workspace_session(engine, workspace, audience) as db:
                assert db.scalar(text("SELECT count(*) FROM customer_events")) == 0
        with (
            pytest.raises(DBAPIError, match="permission denied"),
            workspace_session(engine, core.workspaces[0]) as db,
        ):
            db.execute(text("DELETE FROM customer_events"))
    finally:
        engine.dispose()

    monkeypatch.setenv("EVENT_BATCHES_PER_MINUTE", "1")
    get_settings.cache_clear()
    try:
        assert send(older).status_code == 429
        assert mutate(admin, f"/api-credentials/{key['id']}/revoke", version=1).status_code == 200
        assert send(older).status_code == 401
    finally:
        get_settings.cache_clear()


def test_reference_analytics(core: Core, clients) -> None:
    admin = clients()
    workspace = core.workspaces[0]
    customer = core.records["customer1"]
    member = core.actors["admin1"]["member"]
    contact = core.actors["portala1"]["contact"]
    engine = build_engine(core.migration_url)
    instant = now()
    start = instant - timedelta(days=20)
    stop = instant + timedelta(days=1)
    early = instant - timedelta(days=10)
    recent = instant - timedelta(days=2)
    with workspace_session(engine, workspace) as db:
        config = db.scalar(text("SELECT active_case_config_id FROM workspaces"))
        category = db.scalar(
            text(
                "SELECT definition_json->'categories'->0->>'key' FROM case_config_versions WHERE id=:id"
            ),
            {"id": config},
        )
        assert category
        cases = [uuid4() for _ in range(5)]
        team = uuid4()
        db.execute(
            text(
                "INSERT INTO teams(id,workspace_id,name,version) VALUES (:id,:ws,'Synthetic M4 team',1)"
            ),
            {"id": team, "ws": workspace},
        )
        for i, (created, response, state, number) in enumerate(
            [
                (early, early + timedelta(seconds=10), "open", 2),
                (early, early + timedelta(seconds=31), "resolved", 1),
                (recent, None, "resolved", 1),
                (start - timedelta(days=2), None, "new", 1),
                (stop, None, "new", 1),
            ]
        ):
            db.execute(
                text("""
                INSERT INTO cases (id,workspace_id,number,customer_id,requester_contact_id,config_version_id,
                    category_key,subject,source,state,priority,team_id,assignee_member_id,custom_values,
                    first_response_at,first_response_target_seconds,resolution_target_seconds,
                    last_message_at,current_cycle_number,version,created_at,updated_at)
                VALUES (:id,:ws,:number,:customer,:contact,:config,:category,:subject,'manual_other',
                    :state,'normal',:team,:member,'{}',:response,10,120,:created,:cycle,1,:created,:created)
            """),
                {
                    "id": cases[i],
                    "ws": workspace,
                    "number": 82000 + i,
                    "customer": customer,
                    "contact": contact,
                    "config": config,
                    "category": category,
                    "subject": "=Synthetic" if i == 0 else "Synthetic case",
                    "state": state,
                    "team": team if i != 1 else None,
                    "member": member if state != "new" else None,
                    "response": response,
                    "created": created,
                    "cycle": number,
                },
            )
        resolved1 = early + timedelta(seconds=150)
        resolved2 = early + timedelta(seconds=251)
        resolved3 = recent + timedelta(seconds=120)
        for i, number, opened, resolved, pause, running_pause in [
            (0, 1, early, resolved1, 30, None),
            (
                0,
                2,
                resolved1 + timedelta(days=7),
                None,
                60,
                resolved1 + timedelta(days=7, seconds=181),
            ),
            (1, 1, early, resolved2, 30, None),
            (2, 1, recent, resolved3, 0, None),
            (3, 1, start - timedelta(days=2), None, 0, None),
        ]:
            db.execute(
                text("""
                INSERT INTO case_cycles (id,workspace_id,case_id,cycle_number,opened_at,target_seconds,
                    paused_seconds,pause_started_at,resolved_at,resolved_by_member_id,resolution_code,resolution_summary)
                VALUES (:id,:ws,:case,:number,:opened,120,:pause,:running_pause,:resolved,:member,:code,:summary)
            """),
                {
                    "id": uuid4(),
                    "ws": workspace,
                    "case": cases[i],
                    "number": number,
                    "opened": opened,
                    "pause": pause,
                    "running_pause": running_pause,
                    "resolved": resolved,
                    "member": member if resolved else None,
                    "code": "fixed" if resolved else None,
                    "summary": "Synthetic resolution" if resolved else None,
                },
            )
        for i, submitted, rating in [
            (0, resolved1 + timedelta(seconds=10), 5),
            (1, stop, 2),
            (2, resolved3, 2),
        ]:
            db.execute(
                text("""
                INSERT INTO feedback(id,workspace_id,case_id,cycle_number,requester_contact_id,rating,created_at)
                VALUES (:id,:ws,:case,1,:contact,:rating,:submitted)
            """),
                {
                    "id": uuid4(),
                    "ws": workspace,
                    "case": cases[i],
                    "contact": contact,
                    "rating": rating,
                    "submitted": submitted,
                },
            )
        for i, due, state, completed in [
            (0, early, "completed", early),
            (0, early, "completed", early + timedelta(seconds=1)),
            (1, early, "cancelled", None),
            (0, stop, "open", None),
            (0, start - timedelta(days=1), "completed", early),
            (1, recent, "open", None),
        ]:
            db.execute(
                text("""
                INSERT INTO tasks (id,workspace_id,customer_id,case_id,title,assignee_member_id,
                    due_at,state,completed_at,completed_by_member_id,completion_note,version,created_at)
                VALUES (:id,:ws,:customer,:case,'Synthetic task',:member,:due,:state,:completed,
                    :completer,:note,1,:created)
            """),
                {
                    "id": uuid4(),
                    "ws": workspace,
                    "customer": customer,
                    "case": cases[i],
                    "member": member,
                    "due": due,
                    "state": state,
                    "completed": completed,
                    "completer": member if completed else None,
                    "note": "Synthetic completion" if completed else None,
                    "created": start - timedelta(days=3),
                },
            )

    params = {"from": start.isoformat(), "to": stop.isoformat(), "timezone": "America/New_York"}
    result = admin.get(BASE + "/analytics/overview", params=params)
    assert result.status_code == 200, result.text
    report = result.json()["data"]
    assert report["scope"]["as_of"] == report["trend"]["scope"]["generated_at"]
    assert report["scope"]["today_partial"] is True
    assert report["new_cases"] == 3
    assert (report["active_backlog"], report["unassigned"], report["unanswered_overdue"]) == (
        2,
        1,
        1,
    )
    assert (report["resolution_overdue"], report["paused"]) == (2, 1)
    response_stats = report["first_response"]
    assert response_stats["median_seconds"] == 20.5
    assert response_stats["p90_seconds"] == pytest.approx(28.9)
    assert response_stats["sample_count"] == 2
    assert response_stats["attainment"] == {"numerator": 1, "denominator": 2, "share": 0.5}
    assert report["resolution"]["median_seconds"] == 120
    assert report["resolution"]["p90_seconds"] == pytest.approx(200.8)
    assert report["resolution"]["attainment"]["numerator"] == 2
    assert report["resolution"]["sample_count"] == 3
    assert report["reopen"] == {"numerator": 1, "denominator": 2, "share": 0.5}
    assert report["immature_cycles"] == 1
    assert report["csat"] == {"numerator": 1, "denominator": 2, "share": 0.5}
    assert report["coverage"]["numerator"] == 2 and report["coverage"]["denominator"] == 3
    assert report["follow_up"]["numerator"] == 1 and report["follow_up"]["denominator"] == 3
    assert report["categories"][0]["count"] == 3
    points = report["trend"]["points"]
    assert sum(point["count"] for point in points) == 3
    assert any(point["count"] == 0 and point["categories"][category] == 0 for point in points)
    filtered = admin.get(
        BASE + "/analytics/overview", params={**params, "team_id": str(team), "category": category}
    ).json()["data"]
    assert filtered["new_cases"] == 2 and filtered["first_response"]["sample_count"] == 1
    empty = admin.get(
        BASE + "/analytics/overview",
        params={"from": "2026-03-08", "to": "2026-03-09", "timezone": "America/New_York"},
    ).json()["data"]
    assert empty["scope"]["from_at"] == "2026-03-08T05:00:00Z"
    assert empty["scope"]["to_at"] == "2026-03-09T04:00:00Z"
    assert empty["new_cases"] == 0 and empty["active_backlog"] == 2
    assert empty["first_response"]["median_seconds"] is None and empty["csat"]["share"] is None
    assert (
        admin.get(
            BASE + "/analytics/overview", params={"from": "2024-01-01", "to": "2026-01-01"}
        ).status_code
        == 422
    )
    assert (
        clients("admin2")
        .get(BASE + "/analytics/overview", params=params)
        .json()["data"]["new_cases"]
        == 0
    )
    assert clients("portala1").get(BASE + "/analytics/overview", params=params).status_code == 403
    rows = admin.get(
        BASE + "/analytics/records", params={**params, "metric": "reopen", "limit": 2}
    ).json()
    assert rows["meta"]["has_more"]
    assert len(rows["data"]) == 2 and rows["data"][0]["eligible"] is False
    weekly = admin.get(BASE + "/analytics/trends", params={**params, "bucket": "week"}).json()[
        "data"
    ]
    assert weekly["bucket"] == "week" and sum(row["count"] for row in weekly["points"]) == 3

    export = {**params, "report": "cases"}
    assert clients("agent1").get(BASE + "/analytics/export", params=export).status_code == 403
    response = clients("manager1").get(BASE + "/analytics/export", params=export)
    assert response.status_code == 200, response.text
    csv_rows = list(csv.reader(io.StringIO(response.text)))
    assert csv_rows[0][1] == "generated_at_utc" and csv_rows[1][5] == params["timezone"]
    assert len(csv_rows) == 6 and any("'=Synthetic" in row for row in csv_rows)
    with workspace_session(engine, workspace) as db:
        assert (
            db.scalar(text("SELECT count(*) FROM audit_events WHERE action = 'analytics.exported'"))
            == 1
        )
    engine.dispose()
