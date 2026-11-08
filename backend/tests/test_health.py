import json
import logging
from uuid import UUID

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pytest import LogCaptureFixture, MonkeyPatch

from app.platform.auth import WorkspaceScope, require_workspace
from app.platform.config import Settings


def test_liveness_does_not_need_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}
    request_id = response.json()["meta"]["request_id"]
    assert str(UUID(request_id)) == request_id
    assert response.headers["x-request-id"] == request_id
    assert response.headers["cache-control"] == "no-store"


def test_request_id_cannot_be_forged(client: TestClient) -> None:
    first = client.get("/api/v1/health/live", headers={"X-Request-ID": "untrusted"})
    second = client.get("/api/v1/health/live")
    assert first.headers["x-request-id"] != "untrusted"
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


def test_ready_failure_is_safe(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.platform.health.database_ready", lambda _: False)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["retry-after"] == "5"
    assert response.json()["code"] == "dependency_unavailable"
    assert "postgresql" not in response.text
    assert "password" not in response.text


def test_ready_success_contract(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.platform.health.database_ready", lambda _: True)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ready"}


def test_missing_route_has_problem_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/customers")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_wrong_method_is_not_a_success(client: TestClient) -> None:
    response = client.post("/api/v1/health/live")
    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"


def test_authentication_seam_denies_unverified_workspace(
    application: FastAPI, client: TestClient
) -> None:
    @application.get("/test/private")
    def private(scope: WorkspaceScope = Depends(require_workspace)) -> dict[str, str]:  # noqa: B008
        return {"workspace": str(scope.workspace_id)}

    response = client.get("/test/private", headers={"X-Workspace-ID": "forged"})
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_unexpected_exception_is_redacted(application: FastAPI, client: TestClient) -> None:
    @application.get("/test/error")
    def broken() -> None:
        raise RuntimeError("password=never-log-this")

    response = client.get("/test/error")
    assert response.status_code == 500
    assert "never-log-this" not in response.text
    assert response.json()["code"] == "internal_error"


def test_request_logs_do_not_include_query_content(
    client: TestClient, caplog: LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="atlas.requests"):
        client.get("/api/v1/health/live?token=never-log-this")
    record = next(record for record in caplog.records if record.name == "atlas.requests")
    payload = json.loads(record.message)
    assert payload["route"] == "/health/live"
    assert "never-log-this" not in record.message
    assert set(payload) == {"route", "status", "duration_ms", "request_id"}


def test_configuration_redacts_database_credentials() -> None:
    settings = Settings(database_url="postgresql+psycopg://u:secret-value@localhost/db")
    assert "secret-value" not in repr(settings)
