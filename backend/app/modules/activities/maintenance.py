"""Purge expired recorded activity for one operator-selected workspace."""

import argparse
import os
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, text

from app.modules.activities.models import CustomerEvent
from app.platform.database import build_engine, workspace_session
from app.platform.protocol import now


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=UUID, required=True)
    args = parser.parse_args()
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        parser.error("Set MIGRATION_DATABASE_URL in the operator terminal")
    engine = build_engine(url)
    try:
        with workspace_session(engine, args.workspace) as session:
            if session.scalar(text("SELECT current_user")) != "atlas_migrator":
                parser.error("Retention maintenance requires the migration role")
            purged = (
                session.connection()
                .execute(
                    delete(CustomerEvent).where(
                        CustomerEvent.workspace_id == args.workspace,
                        CustomerEvent.received_at < now() - timedelta(days=180),
                    )
                )
                .rowcount
            )
        print(f"Expired event rows removed: {purged}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
