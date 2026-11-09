"""Private synthetic manager, agent, and case for the Compose browser check."""

import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cases.schemas import CaseCreateStaff
from app.modules.cases.service import create
from app.modules.customers.models import Contact
from app.modules.identity.models import Membership, User
from app.modules.identity.repository import access_scope, workspace_by_slug
from app.modules.identity.security import password_hash
from app.platform.auth import UnitOfWork
from app.platform.database import build_engine, set_scope
from app.platform.protocol import now


def main() -> None:
    destination = Path(__file__).resolve().parents[2] / "tmp" / "m5-browser.json"
    fixture = json.loads(destination.with_name("m2-browser.json").read_text(encoding="utf-8"))
    engine = build_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with Session(engine) as db, db.begin():
            workspace = workspace_by_slug(db, fixture["workspace"])
            assert workspace
            actors = {}
            hashed = password_hash(fixture["password"])
            for role in ("manager", "agent"):
                user = User(
                    normalized_email=f"synthetic-m5-{role}@example.com",
                    display_name=f"Synthetic M5 {role}",
                    password_hash=hashed,
                )
                db.add(user)
                db.flush()
                db.add(
                    Membership(
                        workspace_id=workspace.id,
                        user_id=user.id,
                        role=role,
                        active=True,
                        setup_completed_at=now(),
                    )
                )
                actors[role] = user
                fixture[f"m5_{role}_email"] = user.normalized_email
            db.flush()
            agent = actors["agent"]
            scope = access_scope(db, agent, workspace, "staff", uuid4())
            assert scope
            set_scope(db, workspace.id, "staff", agent.id)
            contact = db.scalar(
                select(Contact).where(Contact.normalized_email == fixture["alpha_email"])
            )
            assert contact
            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/api/v1/cases",
                    "headers": [(b"idempotency-key", uuid4().hex.encode())],
                }
            )
            request.state.request_id = "synthetic-m5-browser"
            case = create(
                UnitOfWork(db, scope),
                CaseCreateStaff(
                    customer_id=contact.customer_id,
                    requester_contact_id=contact.id,
                    category_key="access",
                    subject="Synthetic M5 badge support",
                    description="This fictional case context is outside the knowledge corpus.",
                ),
                request,
            )
            fixture["m5_case_id"] = str(case.id)
        destination.write_text(json.dumps(fixture), encoding="utf-8")
        destination.chmod(0o600)
    finally:
        engine.dispose()
    print("Prepared synthetic M5 browser roles and case")


if __name__ == "__main__":
    main()
