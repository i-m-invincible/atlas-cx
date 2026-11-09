"""Import the implemented model registry for migrations and operator tooling."""

from app.modules.activities.models import CustomerEvent, EventDefinition
from app.modules.cases.models import (
    Case,
    CaseCycle,
    CaseTransition,
    Message,
    ReadMarker,
    WorkspaceCounter,
)
from app.modules.customers.import_models import CustomerImport
from app.modules.customers.models import Contact, Customer
from app.modules.followups.models import Feedback, Task
from app.modules.identity.models import (
    AuthRateLimit,
    LoginSession,
    Membership,
    PortalBinding,
    SetupToken,
    User,
)
from app.modules.workspace.case_config_models import CaseConfig
from app.modules.workspace.credential_models import ApiCredential
from app.modules.workspace.models import Workspace
from app.modules.workspace.team_models import Team, TeamMember
from app.platform.audit import AuditEvent
from app.platform.idempotency import IdempotencyRecord
from app.platform.rate_limits import RateBucket

__all__ = [
    "Workspace",
    "User",
    "Membership",
    "PortalBinding",
    "LoginSession",
    "SetupToken",
    "AuthRateLimit",
    "Customer",
    "Contact",
    "Team",
    "TeamMember",
    "AuditEvent",
    "Case",
    "CaseConfig",
    "CaseCycle",
    "CaseTransition",
    "Message",
    "ReadMarker",
    "WorkspaceCounter",
    "IdempotencyRecord",
    "Feedback",
    "Task",
    "CustomerImport",
    "EventDefinition",
    "CustomerEvent",
    "ApiCredential",
    "RateBucket",
]
