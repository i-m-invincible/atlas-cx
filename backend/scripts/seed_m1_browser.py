"""Synthetic identities for the disposable full-stack CI test, never application startup."""

import json
import os
import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.customers.models import Customer
from app.modules.identity.operator import bootstrap_workspace
from app.platform.database import build_engine

engine = build_engine(os.environ["MIGRATION_DATABASE_URL"])
password = secrets.token_urlsafe(24)
email = "synthetic-browser-admin@example.com"
with Session(engine) as session, session.begin():
    first, _ = bootstrap_workspace(
        session,
        "m1-browser",
        "Synthetic browser workspace",
        email,
        "Synthetic browser administrator",
        password,
    )
    first_id = str(first.id)
    second, _ = bootstrap_workspace(
        session,
        "m1-browser-other",
        "Synthetic other workspace",
        "synthetic-other-admin@example.com",
        "Synthetic other administrator",
        password,
    )
    customer = Customer(
        workspace_id=second.id, name="Other workspace synthetic record", kind="business"
    )
    session.add(customer)
    session.flush()
    other_customer_id = str(customer.id)
destination = Path(__file__).resolve().parents[2] / "tmp" / "m1-browser.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(
    json.dumps(
        {
            "workspace": "m1-browser",
            "workspace_id": first_id,
            "email": email,
            "password": password,
            "other_customer_id": other_customer_id,
        }
    ),
    encoding="utf-8",
)
destination.chmod(0o600)
engine.dispose()
print("Prepared isolated synthetic browser identities; credentials were not printed")
