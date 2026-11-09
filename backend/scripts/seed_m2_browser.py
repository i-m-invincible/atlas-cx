"""Private synthetic fixtures for the disposable Compose browser test only."""

import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import Request
from sqlalchemy.orm import Session

from app.modules.cases.schemas import CaseCreateStaff
from app.modules.cases.service import create
from app.modules.customers.models import Contact, Customer
from app.modules.identity.models import Membership, PortalBinding, User
from app.modules.identity.repository import access_scope, workspace_by_slug
from app.modules.identity.security import password_hash
from app.platform.auth import UnitOfWork
from app.platform.database import build_engine, set_scope
from app.platform.protocol import now


def main() -> None:
    destination = Path(__file__).resolve().parents[2] / "tmp" / "m2-browser.json"
    fixture = json.loads(destination.with_name("m1-browser.json").read_text(encoding="utf-8"))
    engine = build_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with Session(engine) as session, session.begin():
            workspace = workspace_by_slug(session, fixture["workspace"])
            assert workspace
            workspace.is_demo = True
            customer = Customer(
                workspace_id=workspace.id, name="Synthetic M2 shared customer", kind="business"
            )
            session.add(customer)
            session.flush()
            for label in ("alpha", "beta"):
                email = f"synthetic-m2-{label}@example.com"
                contact = Contact(
                    workspace_id=workspace.id,
                    customer_id=customer.id,
                    name=f"Synthetic M2 {label}",
                    normalized_email=email,
                )
                user = User(
                    normalized_email=email,
                    display_name=contact.name,
                    password_hash=password_hash(fixture["password"]),
                )
                session.add_all([contact, user])
                session.flush()
                session.add(
                    PortalBinding(
                        workspace_id=workspace.id,
                        user_id=user.id,
                        contact_id=contact.id,
                        active=True,
                        setup_completed_at=now(),
                    )
                )
                fixture[f"{label}_email"] = email
            session.flush()
            # Flush before switching the transaction-local tenant context.
            other = workspace_by_slug(session, "m1-browser-other")
            assert other
            other.is_demo = True
            from sqlalchemy import select

            member = session.scalar(select(Membership).where(Membership.role == "admin"))
            assert member
            operator = session.get(User, member.user_id)
            assert operator
            scope = access_scope(session, operator, other, "staff", uuid4())
            assert scope
            set_scope(session, other.id, "staff", operator.id)
            contact = Contact(
                workspace_id=other.id,
                customer_id=fixture["other_customer_id"],
                name="Synthetic other requester",
                normalized_email="synthetic-m2-other@example.com",
            )
            session.add(contact)
            session.flush()
            portal_user = User(
                normalized_email=contact.normalized_email,
                display_name=contact.name,
                password_hash=password_hash(fixture["password"]),
            )
            session.add(portal_user)
            session.flush()
            session.add(
                PortalBinding(
                    workspace_id=other.id,
                    user_id=portal_user.id,
                    contact_id=contact.id,
                    active=True,
                    setup_completed_at=now(),
                )
            )
            fixture["other_workspace"] = other.slug
            fixture["other_admin_email"] = operator.normalized_email
            fixture["other_portal_email"] = contact.normalized_email
            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/api/v1/cases",
                    "headers": [(b"idempotency-key", uuid4().hex.encode())],
                }
            )
            request.state.request_id = "synthetic-m2-seed"
            case = create(
                UnitOfWork(session, scope),
                CaseCreateStaff(
                    customer_id=contact.customer_id,
                    requester_contact_id=contact.id,
                    category_key="access",
                    subject="Synthetic other workspace case",
                    description="Must not be visible to the main workspace.",
                ),
                request,
            )
            fixture["other_case_id"] = str(case.id)
        destination.write_text(json.dumps(fixture), encoding="utf-8")
        destination.chmod(0o600)
    finally:
        engine.dispose()
    print("Prepared synthetic M2 browser fixtures; credentials were not printed")


if __name__ == "__main__":
    main()
