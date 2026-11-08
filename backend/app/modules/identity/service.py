from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.customers.models import Contact, Customer
from app.modules.identity.models import (
    AuthRateLimit,
    LoginSession,
    Membership,
    PortalBinding,
    SetupToken,
    User,
)
from app.modules.identity.repository import access_scope, by_email, workspace_by_slug
from app.modules.identity.schemas import LoginInput, SetupInput
from app.modules.identity.security import (
    csrf_for_session,
    digest,
    password_hash,
    token,
    verify_password,
)
from app.modules.workspace.models import Workspace
from app.platform.audit import record_audit
from app.platform.auth import WorkspaceScope
from app.platform.config import get_settings
from app.platform.database import set_scope
from app.platform.protocol import Fault, now


def login(
    session: Session, payload: LoginInput, ip: str, request_id: str
) -> tuple[WorkspaceScope, str, str] | None:
    instant = now()
    start = instant.replace(minute=(instant.minute // 15) * 15, second=0, microsecond=0)
    keys = sorted(["account:" + digest(str(payload.email).lower()), "ip:" + digest(ip)])
    buckets = []
    for key in keys:
        session.execute(
            insert(AuthRateLimit)
            .values(principal_key=key, window_start=start, failures=0)
            .on_conflict_do_nothing()
        )
        bucket = session.scalar(
            select(AuthRateLimit)
            .where(AuthRateLimit.principal_key == key, AuthRateLimit.window_start == start)
            .with_for_update()
        )
        assert bucket
        if bucket.failures >= 5:
            remaining = max(1, int((start + timedelta(minutes=15) - instant).total_seconds()))
            raise Fault(
                429,
                "rate_limited",
                "Too many sign-in attempts. Try again later.",
                {"Retry-After": str(remaining)},
            )
        buckets.append(bucket)
    user = by_email(session, str(payload.email))
    valid_password = verify_password(
        user.password_hash if user else None, payload.password.get_secret_value()
    )
    workspace = workspace_by_slug(session, payload.workspace_slug)
    session_id = uuid4()
    scope = (
        access_scope(session, user, workspace, payload.audience, session_id)
        if valid_password and user and workspace
        else None
    )
    if not scope:
        for bucket in buckets:
            bucket.failures += 1
        return None
    assert user and workspace
    raw = token()
    csrf = csrf_for_session(raw)
    session.add(
        LoginSession(
            id=session_id,
            token_hash=digest(raw),
            csrf_secret_hash=digest(csrf),
            user_id=user.id,
            workspace_id=workspace.id,
            audience=payload.audience,
            expires_at=instant + timedelta(hours=12),
            absolute_expires_at=instant + timedelta(days=7),
            last_seen_at=instant,
        )
    )
    record_audit(
        session, workspace.id, user.id, "auth.login", "session", session_id, [], request_id
    )
    return scope, raw, csrf


def issue_setup(
    session: Session,
    user: User,
    purpose: str,
    workspace_id: object = None,
    membership_id: object = None,
    portal_binding_id: object = None,
) -> str:
    from typing import cast
    from uuid import UUID

    filters = [
        SetupToken.user_id == user.id,
        SetupToken.purpose == purpose,
        SetupToken.used_at.is_(None),
    ]
    if membership_id:
        filters.append(SetupToken.membership_id == membership_id)
    elif portal_binding_id:
        filters.append(SetupToken.portal_binding_id == portal_binding_id)
    session.execute(update(SetupToken).where(*filters).values(used_at=now()))
    raw = token()
    session.add(
        SetupToken(
            token_hash=digest(raw),
            user_id=user.id,
            purpose=purpose,
            workspace_id=cast(UUID | None, workspace_id),
            membership_id=cast(UUID | None, membership_id),
            portal_binding_id=cast(UUID | None, portal_binding_id),
            expires_at=now() + timedelta(hours=24),
        )
    )
    return get_settings().public_origin + "/setup#token=" + raw


def complete_setup(session: Session, payload: SetupInput, request_id: str) -> None:
    setup = session.scalar(
        select(SetupToken)
        .where(SetupToken.token_hash == digest(payload.setup_token.get_secret_value()))
        .with_for_update()
    )
    invalid = Fault(400, "setup_invalid", "This setup link or password is invalid or expired.")
    if not setup or setup.used_at or setup.expires_at <= now():
        raise invalid
    user = session.scalar(select(User).where(User.id == setup.user_id).with_for_update())
    if not user or user.disabled_at:
        raise invalid
    if setup.purpose == "recovery" or user.password_hash is None:
        if not payload.new_password or payload.current_password:
            raise invalid
        user.password_hash = password_hash(payload.new_password.get_secret_value())
        user.updated_at = now()
        session.execute(
            update(LoginSession).where(LoginSession.user_id == user.id).values(revoked_at=now())
        )
    elif (
        not payload.current_password
        or payload.new_password
        or not verify_password(user.password_hash, payload.current_password.get_secret_value())
    ):
        raise invalid
    if setup.workspace_id:
        set_scope(session, setup.workspace_id)
        workspace = session.get(Workspace, setup.workspace_id)
        if not workspace or workspace.archived_at:
            raise invalid
        target: Membership | PortalBinding | None
        if setup.membership_id:
            target = session.get(Membership, setup.membership_id)
        else:
            target = session.get(PortalBinding, setup.portal_binding_id)
        if not target or target.user_id != user.id:
            raise invalid
        if isinstance(target, PortalBinding):
            contact = session.get(Contact, target.contact_id)
            customer = session.get(Customer, contact.customer_id) if contact else None
            if not contact or contact.archived_at or not customer or customer.archived_at:
                raise invalid
        target.active = True
        target.version += 1
        target.updated_at = now()
        record_audit(
            session,
            setup.workspace_id,
            user.id,
            "auth.setup",
            "access",
            target.id,
            ["active"],
            request_id,
        )
    setup.used_at = now()
