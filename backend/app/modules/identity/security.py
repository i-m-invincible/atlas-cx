import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.config import get_settings
from app.platform.protocol import Fault, now

SESSION_COOKIE = "atlas_session"
CSRF_COOKIE = "atlas_csrf"
hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, type=Type.ID)
_dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def token() -> str:
    return secrets.token_urlsafe(32)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str) -> str:
    return hasher.hash(password)


def verify_password(encoded: str | None, password: str) -> bool:
    try:
        valid = hasher.verify(encoded or _dummy_hash, password)
        return bool(encoded) and valid
    except (VerificationError, InvalidHashError):
        return False


def csrf_for_session(raw_token: str) -> str:
    return hmac.new(
        get_settings().session_signing_key.get_secret_value().encode(),
        ("csrf:" + raw_token).encode(),
        hashlib.sha256,
    ).hexdigest()


def anonymous_csrf() -> str:
    payload = f"{int(now().timestamp())}.{token()}"
    signature = hmac.new(
        get_settings().session_signing_key.get_secret_value().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{signature}".encode()).decode()


def check_origin(request: Request) -> None:
    if request.headers.get("Origin") != get_settings().public_origin:
        raise Fault(403, "origin_rejected", "This request must come from the application.")


def check_browser_csrf(request: Request, session: Session) -> None:
    from app.modules.identity.models import LoginSession

    check_origin(request)
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        check_anonymous_csrf(request)
        return
    # CSRF proves browser possession; login/setup do not need to lock or touch
    # the previous identity before establishing their own transaction scope.
    stored = session.scalar(select(LoginSession).where(LoginSession.token_hash == digest(raw)))
    if (
        not stored
        or stored.revoked_at
        or stored.expires_at <= now()
        or stored.absolute_expires_at <= now()
    ):
        raise Fault(401, "unauthenticated", "Your session expired. Sign in to continue.")
    if not hmac.compare_digest(
        digest(request.headers.get("X-CSRF-Token", "")), stored.csrf_secret_hash
    ):
        raise Fault(403, "csrf_rejected", "Refresh this page and try again.")


def check_anonymous_csrf(request: Request) -> None:
    check_origin(request)
    supplied = request.headers.get("X-CSRF-Token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    try:
        if not supplied or len(supplied) > 512 or not hmac.compare_digest(supplied, cookie):
            raise ValueError
        stamp, nonce, signature = base64.urlsafe_b64decode(supplied).decode().split(".")
        expected = hmac.new(
            get_settings().session_signing_key.get_secret_value().encode(),
            f"{stamp}.{nonce}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected) or not (
            0 <= now().timestamp() - int(stamp) <= timedelta(hours=1).total_seconds()
        ):
            raise ValueError
    except (ValueError, UnicodeError):
        raise Fault(403, "csrf_rejected", "Refresh this page and try again.") from None
