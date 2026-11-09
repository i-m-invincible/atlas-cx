"""Bootstrap defaults and shared projections for published configurations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cases.models import WorkspaceCounter
from app.modules.cases.schemas import Definition, PortalConfig, PublicCategory, PublicField
from app.modules.workspace.case_config_models import CaseConfig
from app.modules.workspace.models import Workspace
from app.platform.protocol import Fault, now


def default_definition() -> Definition:
    return Definition.model_validate(
        {
            "categories": [
                {"key": "access", "label": "Access"},
                {"key": "billing_question", "label": "Billing question"},
                {"key": "product_issue", "label": "Product issue"},
            ],
            "state_labels": {
                "new": "New",
                "open": "Open",
                "pending_customer": "Awaiting customer",
                "resolved": "Resolved",
                "closed": "Closed",
            },
            "priorities": {
                key: {"response_minutes": response, "resolution_minutes": resolution}
                for key, response, resolution in [
                    ("urgent", 60, 480),
                    ("high", 240, 1440),
                    ("normal", 480, 2880),
                    ("low", 1440, 5760),
                ]
            },
            "fields": [],
            "portal_default_priority": "normal",
        }
    )


def seed_default(session: Session, workspace: Workspace, administrator_id: UUID) -> None:
    if not workspace.active_case_config_id:
        row = CaseConfig(
            workspace_id=workspace.id,
            number=1,
            status="published",
            definition_json=default_definition().model_dump(mode="json"),
            created_by_member_id=administrator_id,
            published_at=now(),
        )
        session.add(row)
        session.flush()
        workspace.active_case_config_id = row.id
    if not session.get(WorkspaceCounter, workspace.id):
        session.add(WorkspaceCounter(workspace_id=workspace.id, next_case_number=1))
    session.flush()


def published(session: Session, identifier: UUID | None) -> tuple[CaseConfig, Definition]:
    row = session.scalar(
        select(CaseConfig).where(CaseConfig.id == identifier, CaseConfig.status == "published")
    )
    if not row:
        raise Fault(
            503,
            "configuration_unavailable",
            "Case configuration is unavailable. Ask an administrator.",
        )
    return row, Definition.model_validate(row.definition_json)


def public_config(definition: Definition, creating: bool = False) -> PortalConfig:
    return PortalConfig(
        categories=[PublicCategory(key=row.key, label=row.label) for row in definition.categories],
        state_labels=definition.state_labels,
        fields=[
            PublicField(**{key: getattr(field, key) for key in PublicField.model_fields})
            for field in definition.fields
            if field.portal_visible and (not creating or field.portal_editable_on_create)
        ],
    )
