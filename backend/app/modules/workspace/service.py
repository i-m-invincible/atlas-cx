from typing import cast
from uuid import UUID

from fastapi import Request
from sqlalchemy import delete, func, select, update

from app.modules.customers import repository as customers
from app.modules.customers.models import Customer
from app.modules.identity.models import LoginSession, Membership, PortalBinding, SetupToken, User
from app.modules.identity.repository import by_email
from app.modules.identity.schemas import Role
from app.modules.identity.service import issue_setup
from app.modules.workspace.models import Workspace
from app.modules.workspace.schemas import (
    MemberCreate,
    MemberPatch,
    MemberSetupView,
    MemberView,
    PortalSetupView,
    TeamCreate,
    TeamPatch,
    TeamView,
    WorkspacePatch,
    WorkspaceView,
)
from app.modules.workspace.team_models import Team, TeamMember
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role
from app.platform.protocol import Fault, match_version, missing, now


def workspace_view(row: Workspace) -> WorkspaceView:
    return WorkspaceView(
        id=row.id,
        version=row.version,
        name=row.name,
        slug=row.slug,
        timezone=row.timezone,
        feedback_manager_member_id=row.feedback_manager_member_id,
    )


def member_view(uow: UnitOfWork, row: Membership) -> MemberView:
    user = uow.session.get(User, row.user_id)
    assert user
    return MemberView(
        id=row.id,
        version=row.version,
        user_id=row.user_id,
        display_name=(
            user.display_name if row.active else row.invited_display_name or "Inactive member"
        ),
        email=user.normalized_email,
        role=cast(Role, row.role),
        active=row.active,
        created_at=row.created_at,
    )


def eligible_member(uow: UnitOfWork, identifier: UUID, manager: bool = False) -> Membership:
    row = uow.session.get(Membership, identifier)
    roles = {"admin", "manager"} if manager else {"admin", "manager", "agent"}
    if not row or not row.active or row.role not in roles:
        raise Fault(422, "invalid_member", "Choose an active member with the required role.")
    return row


def update_workspace(uow: UnitOfWork, payload: WorkspacePatch, request: Request) -> WorkspaceView:
    require_role(uow.scope, "admin")
    row = uow.session.get(Workspace, uow.scope.workspace_id, with_for_update=True)
    assert row
    match_version(request, row.version)
    changes = payload.model_dump(exclude_unset=True)
    if payload.feedback_manager_member_id:
        eligible_member(uow, payload.feedback_manager_member_id, True)
    for key, value in changes.items():
        setattr(row, key, value)
    row.version += 1
    row.updated_at = now()
    record_audit(
        uow.session,
        row.id,
        uow.scope.user_id,
        "workspace.updated",
        "workspace",
        row.id,
        list(changes),
        request.state.request_id,
    )
    uow.session.flush()
    return workspace_view(row)


def create_member(uow: UnitOfWork, payload: MemberCreate, request: Request) -> MemberSetupView:
    require_role(uow.scope, "admin")
    uow.session.get(Workspace, uow.scope.workspace_id, with_for_update=True)
    user = by_email(uow.session, str(payload.email))
    if not user:
        user = User(normalized_email=str(payload.email).lower(), display_name=payload.display_name)
        uow.session.add(user)
        uow.session.flush()
    member = uow.session.scalar(select(Membership).where(Membership.user_id == user.id))
    if member:
        if member.active:
            raise Fault(
                409, "membership_exists", "This person already has active workspace access."
            )
        match_version(request, member.version)
        member.role = payload.role
        member.invited_display_name = payload.display_name
        member.version += 1
        member.updated_at = now()
    else:
        member = Membership(
            workspace_id=uow.scope.workspace_id,
            user_id=user.id,
            role=payload.role,
            active=False,
            invited_display_name=payload.display_name,
        )
        uow.session.add(member)
    uow.session.flush()
    url = issue_setup(uow.session, user, "staff_setup", uow.scope.workspace_id, member.id)
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "member.setup_created",
        "membership",
        member.id,
        ["role"],
        request.state.request_id,
    )
    return MemberSetupView(member=member_view(uow, member), setup_url=url)


def update_member(
    uow: UnitOfWork, identifier: UUID, payload: MemberPatch, request: Request
) -> MemberView:
    require_role(uow.scope, "admin")
    workspace = uow.session.get(Workspace, uow.scope.workspace_id, with_for_update=True)
    row = uow.session.get(Membership, identifier, with_for_update=True)
    if not row or not workspace:
        raise missing()
    match_version(request, row.version)
    role = payload.role if payload.role is not None else row.role
    active = payload.active if payload.active is not None else row.active
    if active and (
        not row.setup_completed_at
        or not uow.session.scalar(select(User.password_hash).where(User.id == row.user_id))
    ):
        raise Fault(409, "setup_required", "This member must complete their setup link first.")
    if row.role == "admin" and row.active and (role != "admin" or not active):
        count = uow.session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.active.is_(True), Membership.role == "admin")
        )
        if count is None or count <= 1:
            raise Fault(409, "last_administrator", "At least one active administrator must remain.")
    losing_ownership = not active or role == "viewer"
    customers_owned = (
        uow.session.scalar(
            select(func.count()).select_from(Customer).where(Customer.owner_member_id == row.id)
        )
        if losing_ownership
        else 0
    )
    fallback_changes = workspace.feedback_manager_member_id == row.id and (
        not active or role not in {"admin", "manager"}
    )
    if customers_owned or fallback_changes:
        if not payload.replacement_member_id or payload.replacement_member_id == row.id:
            raise Fault(
                409,
                "replacement_required",
                "Choose a replacement for customer ownership and workspace responsibilities "
                "before changing this access.",
            )
        replacement = eligible_member(uow, payload.replacement_member_id, bool(fallback_changes))
        transferred = uow.session.scalars(
            update(Customer)
            .where(Customer.owner_member_id == row.id)
            .values(owner_member_id=replacement.id, version=Customer.version + 1, updated_at=now())
            .returning(Customer.id)
        )
        for customer_id in transferred:
            record_audit(
                uow.session,
                uow.scope.workspace_id,
                uow.scope.user_id,
                "customer.owner_reassigned",
                "customer",
                customer_id,
                ["owner_member_id"],
                request.state.request_id,
                "Ownership transferred during a membership access change.",
            )
        if fallback_changes:
            workspace.feedback_manager_member_id = replacement.id
            workspace.version += 1
            workspace.updated_at = now()
    access_changed = row.active != active or row.role != role
    row.active, row.role = active, role
    row.version += 1
    row.updated_at = now()
    if access_changed:
        if not active:
            uow.session.execute(
                update(SetupToken)
                .where(SetupToken.membership_id == row.id, SetupToken.used_at.is_(None))
                .values(used_at=now())
            )
        uow.session.execute(
            update(LoginSession)
            .where(
                LoginSession.workspace_id == uow.scope.workspace_id,
                LoginSession.user_id == row.user_id,
                LoginSession.audience == "staff",
            )
            .values(revoked_at=now())
        )
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "member.updated",
        "membership",
        row.id,
        list(payload.model_fields_set),
        request.state.request_id,
    )
    uow.session.flush()
    return member_view(uow, row)


def portal_setup(uow: UnitOfWork, identifier: UUID, request: Request) -> PortalSetupView:
    require_role(uow.scope, "admin")
    contact = customers.contact(uow.session, identifier, True)
    match_version(request, contact.version)
    customer = customers.customer(uow.session, contact.customer_id)
    if contact.archived_at or customer.archived_at:
        raise Fault(409, "archived", "Archived records cannot receive portal access.")
    user = by_email(uow.session, contact.normalized_email)
    if not user:
        user = User(normalized_email=contact.normalized_email, display_name=contact.name)
        uow.session.add(user)
        uow.session.flush()
    binding = uow.session.scalar(
        select(PortalBinding).where(PortalBinding.contact_id == identifier)
    )
    if not binding:
        binding = PortalBinding(
            workspace_id=uow.scope.workspace_id,
            user_id=user.id,
            contact_id=identifier,
            active=False,
        )
        uow.session.add(binding)
        uow.session.flush()
    contact.version += 1
    contact.updated_at = now()
    url = issue_setup(
        uow.session, user, "portal_setup", uow.scope.workspace_id, portal_binding_id=binding.id
    )
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "portal.setup_created",
        "contact",
        identifier,
        ["portal_access"],
        request.state.request_id,
    )
    uow.session.flush()
    return PortalSetupView(contact=customers.contact_view(uow.session, contact), setup_url=url)


def portal_access(uow: UnitOfWork, identifier: UUID, active: bool, request: Request) -> object:
    require_role(uow.scope, "admin")
    contact = customers.contact(uow.session, identifier, True)
    match_version(request, contact.version)
    binding = uow.session.scalar(
        select(PortalBinding).where(PortalBinding.contact_id == identifier)
    )
    if not binding:
        raise missing()
    user = uow.session.get(User, binding.user_id)
    customer = customers.customer(uow.session, contact.customer_id)
    if active and (
        not binding.setup_completed_at
        or not user
        or not user.password_hash
        or contact.archived_at
        or customer.archived_at
    ):
        raise Fault(
            409,
            "setup_required",
            "Complete setup and check that the customer and contact are active.",
        )
    binding.active = active
    binding.version += 1
    binding.updated_at = now()
    contact.version += 1
    contact.updated_at = now()
    if not active:
        uow.session.execute(
            update(SetupToken)
            .where(SetupToken.portal_binding_id == binding.id, SetupToken.used_at.is_(None))
            .values(used_at=now())
        )
        uow.session.execute(
            update(LoginSession)
            .where(
                LoginSession.workspace_id == uow.scope.workspace_id,
                LoginSession.user_id == binding.user_id,
                LoginSession.audience == "portal",
            )
            .values(revoked_at=now())
        )
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "portal.access_changed",
        "contact",
        identifier,
        ["active"],
        request.state.request_id,
    )
    uow.session.flush()
    return customers.contact_view(uow.session, contact)


def team_view(uow: UnitOfWork, row: Team) -> TeamView:
    ids = list(
        uow.session.scalars(
            select(TeamMember.member_id)
            .where(TeamMember.team_id == row.id)
            .order_by(TeamMember.member_id)
        )
    )
    return TeamView(
        id=row.id,
        version=row.version,
        name=row.name,
        member_ids=ids,
        archived_at=row.archived_at,
        created_at=row.created_at,
    )


def save_team(
    uow: UnitOfWork,
    payload: TeamCreate | TeamPatch,
    request: Request,
    identifier: UUID | None = None,
) -> TeamView:
    require_role(uow.scope, "admin")
    updating = identifier is not None
    if identifier:
        row = uow.session.get(Team, identifier, with_for_update=True)
        if not row:
            raise missing()
        match_version(request, row.version)
        row.version += 1
        row.updated_at = now()
    else:
        assert isinstance(payload, TeamCreate)
        row = Team(workspace_id=uow.scope.workspace_id, name=payload.name)
        uow.session.add(row)
        uow.session.flush()
    if payload.name:
        row.name = payload.name
    if isinstance(payload, TeamPatch) and payload.archived is not None:
        row.archived_at = now() if payload.archived else None
    if payload.member_ids is not None:
        for identifier in payload.member_ids:
            member = uow.session.get(Membership, identifier)
            if not member or not member.active:
                raise Fault(422, "invalid_member", "Choose active members in this workspace.")
        uow.session.execute(delete(TeamMember).where(TeamMember.team_id == row.id))
        for identifier in payload.member_ids:
            uow.session.add(
                TeamMember(
                    workspace_id=uow.scope.workspace_id, team_id=row.id, member_id=identifier
                )
            )
    uow.session.flush()
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "team.updated" if updating else "team.created",
        "team",
        row.id,
        list(payload.model_fields_set),
        request.state.request_id,
    )
    return team_view(uow, row)
