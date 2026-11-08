"""Operator-only bootstrap and recovery. Passwords are entered through getpass."""

import argparse
import getpass
import os
from uuid import uuid4

from email_validator import validate_email
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.identity.models import Membership, User
from app.modules.identity.repository import by_email, workspace_by_slug
from app.modules.identity.security import password_hash, verify_password
from app.modules.identity.service import issue_setup
from app.modules.workspace.models import Workspace
from app.platform import models  # noqa: F401
from app.platform.audit import record_audit
from app.platform.database import build_engine, set_scope
from app.platform.protocol import now


def bootstrap_workspace(
    session: Session, slug: str, name: str, email: str, display_name: str, password: str
) -> tuple[Workspace, Membership]:
    if session.scalar(text("SELECT current_user")) != "atlas_migrator":
        raise ValueError("Bootstrap requires the separate atlas_migrator operator credential")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Use a password with 12–128 characters")
    email = validate_email(email, check_deliverability=False).normalized.lower()
    import re

    if (
        not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", slug)
        or not name.strip()
        or len(name) > 160
        or not display_name.strip()
        or len(display_name) > 120
    ):
        raise ValueError("Check workspace and account names")
    workspace = workspace_by_slug(session, slug)
    user = by_email(session, email, True)
    if user and (user.disabled_at or not verify_password(user.password_hash, password)):
        raise ValueError("The existing account password is required; bootstrap never resets it")
    if not user:
        user = User(
            normalized_email=email, display_name=display_name, password_hash=password_hash(password)
        )
        session.add(user)
        session.flush()
    if not workspace:
        identifier = uuid4()
        set_scope(session, identifier)
        workspace = Workspace(id=identifier, slug=slug, name=name)
        session.add(workspace)
        session.flush()
    member = session.scalar(select(Membership).where(Membership.user_id == user.id))
    if member:
        if not member.active or member.role != "admin":
            raise ValueError(
                "An existing membership must be changed through workspace administration"
            )
        return workspace, member
    if session.scalar(
        select(Membership.id).where(Membership.active.is_(True), Membership.role == "admin")
    ):
        raise ValueError("This workspace already has an administrator; use a setup link")
    member = Membership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="admin",
        active=True,
        setup_completed_at=now(),
    )
    session.add(member)
    session.flush()
    workspace.feedback_manager_member_id = member.id
    record_audit(
        session,
        workspace.id,
        None,
        "workspace.bootstrapped",
        "workspace",
        workspace.id,
        ["name", "administrator"],
        "operator-bootstrap",
    )
    return workspace, member


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser("bootstrap")
    bootstrap.add_argument("--workspace", required=True)
    bootstrap.add_argument("--name", required=True)
    bootstrap.add_argument("--email", required=True)
    bootstrap.add_argument("--display-name", required=True)
    recovery = commands.add_parser("recover")
    recovery.add_argument("--email", required=True)
    args = parser.parse_args()
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        parser.error("Set MIGRATION_DATABASE_URL in the operator terminal")
    engine = build_engine(url)
    try:
        with Session(engine) as session, session.begin():
            if args.command == "bootstrap":
                password = getpass.getpass(
                    "Administrator password (existing account password if applicable): "
                )
                workspace, _ = bootstrap_workspace(
                    session, args.workspace, args.name, args.email, args.display_name, password
                )
                print(f"Workspace initialized: {workspace.slug}")
            else:
                if session.scalar(text("SELECT current_user")) != "atlas_migrator":
                    raise ValueError("Recovery requires the operator credential")
                user = by_email(session, args.email, True)
                if not user:
                    raise ValueError("Account not found in the operator directory")
                if (
                    input("Confirm identity was verified outside Atlas CX by typing VERIFIED: ")
                    != "VERIFIED"
                ):
                    raise ValueError("Identity verification is required")
                link = issue_setup(session, user, "recovery")
        if args.command == "recover":
            print("Single-use recovery link (share through a verified channel):")
            print(link)
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
