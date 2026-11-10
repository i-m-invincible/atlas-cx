import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.exc import DBAPIError

from app.modules.workspace.models import Workspace
from app.platform.database import build_engine, workspace_session
from app.platform.health import database_ready

pytestmark = pytest.mark.integration


@pytest.fixture
def engines() -> Iterator[tuple[Engine, Engine]]:
    app_url = os.environ.get("TEST_DATABASE_URL")
    migration_url = os.environ.get("MIGRATION_DATABASE_URL")
    assert app_url and migration_url, "Integration tests require explicit test and migration URLs"
    app_engine = build_engine(app_url)
    migration_engine = build_engine(migration_url)
    yield app_engine, migration_engine
    app_engine.dispose()
    migration_engine.dispose()


@pytest.fixture
def workspaces(engines: tuple[Engine, Engine]) -> Iterator[tuple[UUID, UUID]]:
    _, migration_engine = engines
    identifiers = (uuid4(), uuid4())
    for identifier in identifiers:
        with workspace_session(migration_engine, identifier) as session:
            session.add(Workspace(id=identifier, slug=f"test-{identifier}", name="Test workspace"))
    yield identifiers
    for identifier in identifiers:
        with workspace_session(migration_engine, identifier) as session:
            session.execute(delete(Workspace).where(Workspace.id == identifier))


def test_app_role_and_migration_readiness(engines: tuple[Engine, Engine]) -> None:
    app_engine, _ = engines
    assert database_ready(app_engine)
    with app_engine.connect() as connection:
        assert connection.scalar(text("SELECT current_user")) == "atlas_app"
        flags = connection.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        assert flags == (False, False)
        assert connection.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE oid = 'workspaces'::regclass"
            )
        ).one() == (True, True)
        assert connection.scalar(text("SELECT '[1,2,3]'::vector <-> '[1,2,3]'::vector")) == 0


def test_missing_scope_fails_closed(
    engines: tuple[Engine, Engine], workspaces: tuple[UUID, UUID]
) -> None:
    app_engine, _ = engines
    with app_engine.connect() as connection:
        assert connection.execute(text("SELECT id FROM workspaces")).all() == []
    with pytest.raises(DBAPIError), workspace_session(app_engine, uuid4()) as session:
        session.add(Workspace(id=workspaces[0], slug="forbidden", name="Forbidden"))
        session.flush()


def test_cross_workspace_reads_and_writes_are_denied(
    engines: tuple[Engine, Engine], workspaces: tuple[UUID, UUID]
) -> None:
    app_engine, _ = engines
    first, second = workspaces
    with workspace_session(app_engine, first) as session:
        assert session.scalars(select(Workspace.id)).all() == [first]
        assert session.get(Workspace, second) is None
        result = session.execute(
            text("UPDATE workspaces SET name = 'forbidden' WHERE id = :id"), {"id": second}
        )
        assert result.rowcount == 0  # type: ignore[attr-defined]
    with pytest.raises(DBAPIError), workspace_session(app_engine, first) as session:
        session.add(Workspace(id=uuid4(), slug=f"test-{uuid4()}", name="Forbidden"))
        session.flush()


def test_scope_is_transaction_local(
    engines: tuple[Engine, Engine], workspaces: tuple[UUID, UUID]
) -> None:
    app_engine, _ = engines
    for identifier in workspaces:
        with workspace_session(app_engine, identifier) as session:
            assert session.scalars(select(Workspace.id)).all() == [identifier]
    with app_engine.connect() as connection:
        assert connection.execute(text("SELECT id FROM workspaces")).all() == []


def test_owner_role_cannot_make_api_ready(engines: tuple[Engine, Engine]) -> None:
    _, migration_engine = engines
    assert not database_ready(migration_engine)
