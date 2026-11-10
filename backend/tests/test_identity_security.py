from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app.modules.customers.schemas import CustomerCreate, CustomerPatch
from app.modules.identity.schemas import LoginInput
from app.modules.identity.security import (
    anonymous_csrf,
    check_anonymous_csrf,
    csrf_for_session,
    digest,
    password_hash,
    token,
    verify_password,
)
from app.platform.config import Settings, get_settings
from app.platform.protocol import Fault, read_cursor, sign_cursor


def test_argon2id_hash_is_salted_and_verifiable() -> None:
    first = password_hash("synthetic-password-42")
    second = password_hash("synthetic-password-42")
    assert first.startswith("$argon2id$")
    assert first != second
    assert verify_password(first, "synthetic-password-42")
    assert not verify_password(first, "wrong-password")
    assert not verify_password(None, "wrong-password")


def test_opaque_tokens_have_no_identity_payload() -> None:
    first, second = token(), token()
    assert first != second and len(first) >= 43
    assert digest(first) != first
    assert len(digest(first)) == 64
    assert csrf_for_session(first) != csrf_for_session(second)


def test_anonymous_csrf_cookie_is_secure_and_no_store(client: TestClient) -> None:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    assert response.json()["data"]["csrf_token"]
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("origin", [None, "https://other.example", "null"])
def test_login_rejects_missing_or_forged_origin(client: TestClient, origin: str | None) -> None:
    headers = {"Origin": origin} if origin else {}
    response = client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={
            "workspace_slug": "workspace",
            "audience": "staff",
            "email": "staff@example.com",
            "password": "synthetic-password-42",
        },
    )
    assert response.status_code == 403


def test_anonymous_csrf_rejects_tampering_and_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.identity import security

    good = anonymous_csrf()

    def request(value: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [
                    (b"origin", get_settings().public_origin.encode()),
                    (b"x-csrf-token", value.encode()),
                    (b"cookie", f"atlas_csrf={value}".encode()),
                ],
            }
        )

    check_anonymous_csrf(request(good))
    with pytest.raises(Fault):
        check_anonymous_csrf(request(good[:-3] + "abc"))
    later = security.now() + timedelta(hours=2)
    monkeypatch.setattr(security, "now", lambda: later)
    with pytest.raises(Fault):
        check_anonymous_csrf(request(good))


def test_cursors_are_bound_to_workspace_resource_and_filters() -> None:
    binding = {"workspace": "one", "resource": "customers", "q": "needle"}
    value = sign_cursor(binding, ["name", "identifier"])
    assert read_cursor(value, binding) == ["name", "identifier"]
    for changed in (
        {**binding, "workspace": "two"},
        {**binding, "q": "other"},
        {**binding, "resource": "contacts"},
    ):
        with pytest.raises(Fault):
            read_cursor(value, changed)
    with pytest.raises(Fault):
        read_cursor(value[:-1] + ("0" if value[-1] != "0" else "1"), binding)


def test_unknown_fields_blank_names_and_naive_dates_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CustomerCreate(name=" ", kind="business")
    with pytest.raises(ValidationError):
        CustomerCreate(name="Customer", kind="business", workspace_id="forged")
    with pytest.raises(ValidationError):
        CustomerCreate(name="Customer", kind="business", tags=["duplicate", "duplicate"])
    with pytest.raises(ValidationError):
        CustomerCreate(name="Customer", kind="business", tracking_started_at="2026-11-08T12:00:00")
    with pytest.raises(ValidationError):
        CustomerPatch()
    with pytest.raises(ValidationError):
        CustomerPatch(name=None)


def test_passwords_are_redacted_and_spaces_are_preserved() -> None:
    payload = LoginInput(
        workspace_slug="workspace",
        audience="staff",
        email="staff@example.com",
        password=" secret password ",
    )
    assert "secret password" not in repr(payload)
    assert payload.password.get_secret_value() == " secret password "


def test_production_requires_real_keys_and_https() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production")
