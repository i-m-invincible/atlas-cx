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


def set_scope(
    session: Session,
    workspace_id: UUID,
    audience: str = "staff",
    user_id: UUID | None = None,
    contact_id: UUID | None = None,
) -> None:
    for key, value in {
        "workspace_id": str(workspace_id),
        "audience": audience,
        "user_id": str(user_id) if user_id else "",
        "contact_id": str(contact_id) if contact_id else "",
        "login_workspace": "",
    }.items():
        session.execute(
            text("SELECT set_config(:key, :value, true)"), {"key": f"app.{key}", "value": value}
        )


@contextmanager
def workspace_session(
    engine: Engine,
    workspace_id: UUID,
    audience: str = "staff",
    user_id: UUID | None = None,
    contact_id: UUID | None = None,
) -> Iterator[Session]:
    """Call only with workspace scope obtained from a verified session or trusted job.

    set_config(..., true) ends at commit/rollback, preventing pooled connections
    from carrying one workspace's scope into the next transaction.
    """
    with Session(engine) as session, session.begin():
        set_scope(session, workspace_id, audience, user_id, contact_id)
        yield session
