from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.identity.models import LoginSession, User
from app.modules.identity.repository import authenticate, identity_view
from app.modules.identity.schemas import (
    CsrfView,
    IdentityView,
    LoginInput,
    MessageView,
    PasswordInput,
    SetupInput,
)
from app.modules.identity.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    anonymous_csrf,
    check_browser_csrf,
    csrf_for_session,
    password_hash,
    verify_password,
)
from app.modules.identity.service import complete_setup, login
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, authenticated_uow
from app.platform.database import set_scope
from app.platform.protocol import Envelope, Fault, now, result

router = APIRouter(prefix="/auth", tags=["identity"])
Uow = Annotated[UnitOfWork, Depends(authenticated_uow, scope="function")]


@router.get("/csrf", response_model=Envelope[CsrfView])
def csrf(request: Request, response: Response) -> Envelope[CsrfView]:
    origin = request.headers.get("Origin")
    from app.platform.config import get_settings

    if (origin and origin != get_settings().public_origin) or request.headers.get(
        "Sec-Fetch-Site"
    ) == "cross-site":
        raise Fault(403, "origin_rejected", "This request must come from the application.")
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        try:
            with Session(request.app.state.engine) as session, session.begin():
                authenticate(session, raw)
                return result(request, CsrfView(csrf_token=csrf_for_session(raw)))
        except Fault:
            response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax")
    value = anonymous_csrf()
    response.set_cookie(
        CSRF_COOKIE, value, secure=True, httponly=True, samesite="lax", max_age=3600, path="/"
    )
    return result(request, CsrfView(csrf_token=value))


@router.post("/login", response_model=Envelope[IdentityView])
def sign_in(payload: LoginInput, request: Request, response: Response) -> Envelope[IdentityView]:
    with Session(request.app.state.engine) as session, session.begin():
        check_browser_csrf(request, session)
        outcome = login(
            session,
            payload,
            request.client.host if request.client else "unknown",
            request.state.request_id,
        )
        if outcome:
            scope, raw, _ = outcome
            # A successful sign-in rotates any previous browser session.
            old = request.cookies.get(SESSION_COOKIE)
            if old:
                from app.modules.identity.security import digest

                session.execute(
                    update(LoginSession)
                    .where(LoginSession.token_hash == digest(old))
                    .values(revoked_at=now())
                )
            identity = identity_view(session, scope)
    if not outcome:
        raise Fault(401, "invalid_credentials", "The workspace, email, or password is incorrect.")
    response.set_cookie(
        SESSION_COOKIE, raw, secure=True, httponly=True, samesite="lax", max_age=7 * 86400, path="/"
    )
    response.delete_cookie(CSRF_COOKIE, secure=True, httponly=True, samesite="lax")
    return result(request, identity)


@router.get("/me", response_model=Envelope[IdentityView])
def me(request: Request, uow: Uow) -> Envelope[IdentityView]:
    return result(request, identity_view(uow.session, uow.scope))


@router.post("/logout", status_code=204)
def sign_out(request: Request, uow: Uow) -> Response:
    stored = uow.session.get(LoginSession, uow.scope.session_id)
    assert stored
    stored.revoked_at = now()
    set_scope(uow.session, uow.scope.workspace_id)
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "auth.logout",
        "session",
        stored.id,
        [],
        request.state.request_id,
    )
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax")
    return response


@router.post("/password", response_model=Envelope[MessageView])
def change_password(
    payload: PasswordInput, request: Request, response: Response, uow: Uow
) -> Envelope[MessageView]:
    user = uow.session.get(User, uow.scope.user_id, with_for_update=True)
    assert user
    if not verify_password(user.password_hash, payload.current_password.get_secret_value()):
        raise Fault(400, "password_invalid", "The current password is incorrect.")
    user.password_hash = password_hash(payload.new_password.get_secret_value())
    user.updated_at = now()
    uow.session.execute(
        update(LoginSession).where(LoginSession.user_id == user.id).values(revoked_at=now())
    )
    set_scope(uow.session, uow.scope.workspace_id)
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        user.id,
        "auth.password_changed",
        "user",
        user.id,
        ["password"],
        request.state.request_id,
    )
    response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax")
    return result(request, MessageView(message="Password changed. Sign in again."))


@router.post("/setup", response_model=Envelope[MessageView])
def setup(payload: SetupInput, request: Request) -> Envelope[MessageView]:
    with Session(request.app.state.engine) as session, session.begin():
        check_browser_csrf(request, session)
        complete_setup(session, payload, request.state.request_id)
    return result(request, MessageView(message="Access set up. You can sign in now."))
