import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any, TypeVar

from fastapi import Request, Response
from pydantic import BaseModel, ConfigDict

from app.platform.config import get_settings

T = TypeVar("T")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Meta(BaseModel):
    request_id: str
    next_cursor: str | None = None
    has_more: bool = False


class Envelope[T](BaseModel):
    data: T
    meta: Meta


class Fault(Exception):
    def __init__(self, status: int, code: str, detail: str, headers: dict[str, str] | None = None):
        self.status, self.code, self.detail, self.headers = status, code, detail, headers


def now() -> datetime:
    return datetime.now(UTC)


def result[T](request: Request, data: T, response: Response | None = None) -> Envelope[T]:
    if response is not None and hasattr(data, "version"):
        response.headers["ETag"] = f'"{data.version}"'
    return Envelope(data=data, meta=Meta(request_id=request.state.request_id))


def match_version(request: Request, version: int) -> None:
    tag = request.headers.get("If-Match")
    if not tag:
        raise Fault(428, "precondition_required", "Reload the record before making this change.")
    if tag != f'"{version}"':
        raise Fault(
            409,
            "version_conflict",
            "This record changed. Your changes have not been saved.",
            {"ETag": f'"{version}"'},
        )


def missing() -> Fault:
    return Fault(404, "not_found", "This record isn’t available.")


def sign_cursor(binding: dict[str, Any], value: list[str]) -> str:
    raw = json.dumps(
        {"binding": binding, "value": value}, sort_keys=True, separators=(",", ":")
    ).encode()
    payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = hmac.new(
        get_settings().cursor_signing_key.get_secret_value().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def read_cursor(cursor: str, binding: dict[str, Any]) -> list[str]:
    try:
        if len(cursor) > 4096:
            raise ValueError
        payload, signature = cursor.split(".")
        expected = hmac.new(
            get_settings().cursor_signing_key.get_secret_value().encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        body = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        value = body["value"]
        if (
            body["binding"] != binding
            or not isinstance(value, list)
            or not all(isinstance(part, str) for part in value)
        ):
            raise ValueError
        return value
    except (ValueError, KeyError, TypeError):
        raise Fault(
            400, "invalid_cursor", "This page link is invalid. Return to the first page."
        ) from None
