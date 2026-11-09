"""Purge expired CSV staging for one workspace using the migration credential."""

import argparse
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.customers.import_service import purge_expired
from app.modules.identity.repository import workspace_by_slug
from app.modules.workspace.models import Workspace
from app.platform.database import build_engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace")
    args = parser.parse_args()
    engine = build_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with Session(engine) as session, session.begin():
            if session.scalar(text("SELECT current_user")) != "atlas_migrator":
                raise SystemExit("Use the migration credential.")
            workspace = workspace_by_slug(session, args.workspace)
            if not workspace:
                raise SystemExit("Workspace unavailable.")
            session.get(Workspace, workspace.id, with_for_update={"key_share": True})
            count = purge_expired(session)
        print(f"Cleared expired staging for {count} imports.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
