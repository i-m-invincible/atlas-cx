from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException


@dataclass(frozen=True)
class WorkspaceScope:
    workspace_id: UUID
    user_id: UUID


def require_workspace() -> WorkspaceScope:
    """Deny by default until M1 verifies opaque staff/portal sessions.

    No HTTP endpoint accepts a workspace header as authentication. Health routes
    are public and do not need this dependency. M1 replaces this deny-only seam.
    """
    raise HTTPException(status_code=401, detail="Sign in to continue.")
