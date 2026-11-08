from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def build_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )


@contextmanager
def workspace_session(engine: Engine, workspace_id: UUID) -> Iterator[Session]:
    """Call only with workspace scope obtained from a verified session or trusted job.

    set_config(..., true) ends at commit/rollback, preventing pooled connections
    from carrying one workspace's scope into the next transaction.
    """
    with Session(engine) as session, session.begin():
        session.execute(
            text("SELECT set_config('app.workspace_id', :workspace_id, true)"),
            {"workspace_id": str(workspace_id)},
        )
        yield session
