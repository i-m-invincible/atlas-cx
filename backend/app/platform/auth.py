import hmac
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.modules.identity.security import SESSION_COOKIE, check_origin, digest
from app.platform.database import set_scope
from app.platform.protocol import Fault


@dataclass(frozen=True)
class WorkspaceScope:
    workspace_id: UUID
    user_id: UUID
    session_id: UUID
    audience: Literal["staff", "portal"]
    role: str | None
    member_id: UUID | None
    contact_id: UUID | None


@dataclass
class UnitOfWork:
    session: Session
    scope: WorkspaceScope


def authenticated_uow(request: Request) -> Iterator[UnitOfWork]:
    from app.modules.identity.repository import authenticate

    raw = request.cookies.get(SESSION_COOKIE, "")
    if not raw:
        raise Fault(401, "unauthenticated", "Sign in to continue.")
    changing = request.method not in {"GET", "HEAD", "OPTIONS"}
    if changing:
        check_origin(request)
    with Session(request.app.state.engine) as session, session.begin():
        scope, stored = authenticate(session, raw)
        if changing and not hmac.compare_digest(
            digest(request.headers.get("X-CSRF-Token", "")), stored.csrf_secret_hash
        ):
            raise Fault(403, "csrf_rejected", "Refresh this page and try again.")
        set_scope(session, scope.workspace_id, scope.audience, scope.user_id, scope.contact_id)
        request.state.principal = scope
        yield UnitOfWork(session=session, scope=scope)


def staff_uow(request: Request) -> Iterator[UnitOfWork]:
    for uow in authenticated_uow(request):
        require_role(uow.scope, "admin", "manager", "agent", "viewer")
        yield uow


def require_role(scope: WorkspaceScope, *roles: str) -> None:
    if scope.audience != "staff" or scope.role not in roles:
        raise Fault(403, "forbidden", "You don’t have permission to make this change.")


def require_workspace(request: Request) -> WorkspaceScope:
    scope = None
    for uow in authenticated_uow(request):
        scope = uow.scope
    if scope is None:
        raise Fault(401, "unauthenticated", "Sign in to continue.")
    return scope
