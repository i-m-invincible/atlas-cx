from typing import Literal, cast
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select

from app.modules.cases.schemas import ConfigView, Definition, valid_field_value
from app.modules.identity.models import Membership
from app.modules.workspace.case_config_models import CaseConfig
from app.modules.workspace.models import Workspace
from app.modules.workspace.team_models import Team
from app.platform import idempotency
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role
from app.platform.protocol import Fault, Input, match_version, missing, now


def view(row: CaseConfig) -> ConfigView:
    return ConfigView(
        id=row.id,
        version=row.version,
        number=row.number,
        status=cast(Literal["draft", "published"], row.status),
        definition=Definition.model_validate(row.definition_json),
        published_at=row.published_at,
    )


def get(uow: UnitOfWork, identifier: UUID, lock: bool = False) -> CaseConfig:
    row = uow.session.get(CaseConfig, identifier, with_for_update=lock)
    if not row or (row.status != "published" and uow.scope.role != "admin"):
        raise missing()
    return row


def audit(uow: UnitOfWork, row: CaseConfig, action: str, request: Request) -> None:
    record_audit(
        uow.session,
        row.workspace_id,
        uow.scope.user_id,
        action,
        "case_config",
        row.id,
        ["status", "definition"],
        request.state.request_id,
    )


def save(
    uow: UnitOfWork, definition: Definition, request: Request, identifier: UUID | None = None
) -> CaseConfig:
    require_role(uow.scope, "admin")
    if identifier:
        row = get(uow, identifier, True)
        match_version(request, row.version)
        if row.status != "draft":
            raise Fault(409, "published_config", "Create a new draft to change this configuration.")
        row.definition_json = definition.model_dump(mode="json")
        row.version += 1
        row.updated_at = now()
    else:
        assert uow.scope.member_id
        number = uow.session.scalar(select(func.max(CaseConfig.number))) or 0
        row = CaseConfig(
            workspace_id=uow.scope.workspace_id,
            number=number + 1,
            status="draft",
            definition_json=definition.model_dump(mode="json"),
            created_by_member_id=uow.scope.member_id,
        )
        uow.session.add(row)
    uow.session.flush()
    audit(
        uow,
        row,
        "case_config.draft_updated" if identifier else "case_config.draft_created",
        request,
    )
    return row


def validate_fields(definition: Definition) -> None:
    for field in definition.fields:
        editable = field.portal_editable_on_create
        numeric = field.type in {"integer", "decimal"}
        if editable and not field.portal_visible:
            raise Fault(
                422, "invalid_field", f"{field.label}: show fields that customers can edit."
            )
        if field.required_on_create and not editable and field.default is None:
            raise Fault(
                422, "invalid_field", f"{field.label}: provide a default or allow portal entry."
            )
        if field.type == "single_select":
            if not field.allowed_values or len(set(field.allowed_values)) != len(
                field.allowed_values
            ):
                raise Fault(422, "invalid_field", f"{field.label}: supply unique select options.")
        elif field.allowed_values:
            raise Fault(
                422, "invalid_field", f"{field.label}: only single-select fields use options."
            )
        if (field.minimum is not None or field.maximum is not None) and not numeric:
            raise Fault(422, "invalid_field", f"{field.label}: only numeric fields use bounds.")
        if (
            field.minimum is not None
            and field.maximum is not None
            and field.minimum > field.maximum
        ):
            raise Fault(422, "invalid_field", f"{field.label}: maximum must be at least minimum.")
        if field.default is not None and not valid_field_value(field, field.default):
            raise Fault(422, "invalid_field", f"{field.label}: review the default value.")


def publish(uow: UnitOfWork, identifier: UUID, request: Request) -> CaseConfig:
    require_role(uow.scope, "admin")
    row = get(uow, identifier, True)
    replay, exists = idempotency.prepare(uow, request, Input())
    if exists:
        return row
    match_version(request, row.version)
    if row.status != "draft":
        raise Fault(409, "published_config", "This version has already been published.")
    definition = Definition.model_validate(row.definition_json)
    validate_fields(definition)
    for category in definition.categories:
        if category.default_team_id:
            team = uow.session.get(Team, category.default_team_id)
            if not team or team.archived_at:
                raise Fault(
                    422,
                    "invalid_routing_team",
                    f"{category.label}: choose an active workspace team.",
                )
    workspace = uow.session.get(Workspace, uow.scope.workspace_id)
    assert workspace
    manager = (
        uow.session.get(Membership, workspace.feedback_manager_member_id)
        if workspace.feedback_manager_member_id
        else None
    )
    if not manager or not manager.active or manager.role not in {"admin", "manager"}:
        raise Fault(
            409, "feedback_manager_required", "Choose an active feedback manager before publishing."
        )
    row.status = "published"
    row.published_at = row.updated_at = now()
    row.version += 1
    workspace.active_case_config_id = row.id
    workspace.version += 1
    workspace.updated_at = row.updated_at
    audit(uow, row, "case_config.published", request)
    idempotency.complete(replay, "case_config", row.id)
    uow.session.flush()
    return row
