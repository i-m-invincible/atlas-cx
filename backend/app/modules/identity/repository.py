"""Exact identity lookups only; never expose a global user collection."""

from datetime import timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.customers.models import Contact, Customer
from app.modules.identity.models import LoginSession, Membership, PortalBinding, User
from app.modules.identity.schemas import IdentityView, Role
from app.modules.identity.security import digest
from app.modules.workspace.models import Workspace
from app.platform.auth import WorkspaceScope
from app.platform.database import set_scope
from app.platform.protocol import Fault, now


def by_email(session: Session, email: str, lock: bool = False) -> User | None:
    query = select(User).where(User.normalized_email == email.strip().lower())
    return session.scalar(query.with_for_update() if lock else query)


def workspace_by_slug(session: Session, slug: str) -> Workspace | None:
    session.execute(text("SELECT set_config('app.login_workspace', :slug, true)"), {"slug": slug})
    workspace = session.scalar(select(Workspace).where(Workspace.slug == slug))
    session.execute(text("SELECT set_config('app.login_workspace', '', true)"))
    if workspace:
        set_scope(session, workspace.id)
    return workspace


def access_scope(
    session: Session, user: User, workspace: Workspace, audience: str, session_id: UUID
) -> WorkspaceScope | None:

    if user.disabled_at or workspace.archived_at:
        return None
    member_id, contact_id, role = None, None, None
    if audience == "staff":
        member = session.scalar(
            select(Membership).where(Membership.user_id == user.id).with_for_update()
        )
        if not member or not member.active:
            return None
        member_id, role = member.id, member.role
    else:
        binding = session.scalar(
            select(PortalBinding).where(PortalBinding.user_id == user.id).with_for_update()
        )
        if not binding or not binding.active:
            return None
        contact = session.get(Contact, binding.contact_id)
        customer = session.get(Customer, contact.customer_id) if contact else None
        if not contact or contact.archived_at or not customer or customer.archived_at:
            return None
        contact_id = contact.id
    return WorkspaceScope(
        workspace.id,
        user.id,
        session_id,
        cast(Literal["staff", "portal"], audience),
        role,
        member_id,
        contact_id,
    )


def authenticate(session: Session, raw: str) -> tuple[WorkspaceScope, LoginSession]:
    if len(raw) > 128:
        raise Fault(401, "unauthenticated", "Your session expired. Sign in to continue.")
    stored = session.scalar(
        select(LoginSession).where(LoginSession.token_hash == digest(raw)).with_for_update()
    )
    instant = now()
    if (
        not stored
        or stored.revoked_at
        or stored.expires_at <= instant
        or stored.absolute_expires_at <= instant
    ):
        raise Fault(401, "unauthenticated", "Your session expired. Sign in to continue.")
    set_scope(session, stored.workspace_id)
    workspace, user = session.get(Workspace, stored.workspace_id), session.get(User, stored.user_id)
    scope = (
        access_scope(session, user, workspace, stored.audience, stored.id)
        if user and workspace
        else None
    )
    if not scope:
        raise Fault(401, "unauthenticated", "Your session expired. Sign in to continue.")
    stored.last_seen_at = instant
    stored.expires_at = min(instant + timedelta(hours=12), stored.absolute_expires_at)
    return scope, stored


def identity_view(session: Session, scope: WorkspaceScope) -> IdentityView:
    workspace = session.get(Workspace, scope.workspace_id)
    user = session.get(User, scope.user_id)
    assert user and workspace
    permissions = []
    if scope.audience == "staff":
        permissions.append("customers:read")
        if scope.role != "viewer":
            permissions.append("customers:write")
        if scope.role in {"admin", "manager"}:
            permissions.extend(["customers:archive", "audit:read"])
        if scope.role == "admin":
            permissions.append("workspace:manage")
    return IdentityView(
        user_id=user.id,
        display_name=user.display_name,
        email=user.normalized_email,
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        workspace_slug=workspace.slug,
        timezone=workspace.timezone,
        audience=scope.audience,
        role=cast(Role | None, scope.role),
        member_id=scope.member_id,
        contact_id=scope.contact_id,
        permissions=permissions,
        capabilities={"customers": scope.audience == "staff", "cases": False, "rag": False},
    )
