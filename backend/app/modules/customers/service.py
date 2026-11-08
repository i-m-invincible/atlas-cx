from uuid import UUID

from fastapi import Request
from sqlalchemy import select, update

from app.modules.customers import repository
from app.modules.customers.models import Contact, Customer
from app.modules.customers.schemas import (
    ArchiveInput,
    ContactCreate,
    ContactPatch,
    ContactView,
    CustomerCreate,
    CustomerPatch,
    CustomerView,
)
from app.modules.identity.models import Membership, PortalBinding, SetupToken
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role
from app.platform.protocol import Fault, match_version, now


def validate_owner(uow: UnitOfWork, member_id: UUID | None) -> None:
    if member_id:
        member = uow.session.get(Membership, member_id)
        if not member or not member.active or member.role == "viewer":
            raise Fault(
                422, "invalid_owner", "Choose an active staff member who can own customer work."
            )


def save_customer(
    uow: UnitOfWork,
    payload: CustomerCreate | CustomerPatch,
    request: Request,
    identifier: UUID | None = None,
) -> CustomerView:
    require_role(uow.scope, "admin", "manager", "agent")
    changes = payload.model_dump(exclude_unset=identifier is not None)
    if changes.get("external_id"):
        duplicate = uow.session.scalar(
            select(Customer.id).where(
                Customer.external_id == changes["external_id"], Customer.id != identifier
            )
            if identifier
            else select(Customer.id).where(Customer.external_id == changes["external_id"])
        )
        if duplicate:
            raise Fault(
                409,
                "duplicate_external_id",
                "This external ID is already in use in this workspace. "
                "Review the existing customer.",
            )
    validate_owner(uow, changes.get("owner_member_id"))
    if identifier:
        row = repository.customer(uow.session, identifier, True)
        match_version(request, row.version)
        if row.archived_at:
            raise Fault(409, "archived", "Archived customers cannot be changed.")
        if (
            "external_id" in changes
            and row.external_id is not None
            and changes["external_id"] != row.external_id
        ):
            raise Fault(409, "identity_immutable", "An existing external ID cannot be changed.")
        for key, value in changes.items():
            setattr(row, key, value)
        row.version += 1
        row.updated_at = now()
    else:
        row = Customer(workspace_id=uow.scope.workspace_id, **changes)
        uow.session.add(row)
    uow.session.flush()
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "customer.updated" if identifier else "customer.created",
        "customer",
        row.id,
        list(changes),
        request.state.request_id,
    )
    return repository.customer_view(uow.session, row)


def save_contact(
    uow: UnitOfWork,
    payload: ContactCreate | ContactPatch,
    request: Request,
    identifier: UUID | None = None,
) -> ContactView:
    require_role(uow.scope, "admin", "manager", "agent")
    changes = payload.model_dump(exclude_unset=identifier is not None)
    if changes.get("email"):
        query = select(Contact.id).where(Contact.normalized_email == str(changes["email"]).lower())
        if identifier:
            query = query.where(Contact.id != identifier)
        if uow.session.scalar(query):
            raise Fault(
                409,
                "duplicate_contact_email",
                "This email already belongs to a contact in this workspace. "
                "Review the existing contact.",
            )
    if identifier:
        row = repository.contact(uow.session, identifier, True)
        match_version(request, row.version)
        if row.archived_at:
            raise Fault(409, "archived", "Archived contacts cannot be changed.")
        if (
            "email" in changes
            and uow.session.scalar(
                select(PortalBinding.id).where(PortalBinding.contact_id == row.id)
            )
            and str(changes["email"]).lower() != row.normalized_email
        ):
            raise Fault(
                409,
                "portal_identity_bound",
                "Email cannot change after portal access has been provisioned.",
            )
        row.version += 1
        row.updated_at = now()
    else:
        assert isinstance(payload, ContactCreate)
        row = Contact(workspace_id=uow.scope.workspace_id, customer_id=payload.customer_id)
    parent = repository.customer(uow.session, row.customer_id)
    if parent.archived_at:
        raise Fault(409, "archived", "Contacts of an archived customer cannot be changed.")
    for key, value in changes.items():
        if key == "email":
            row.normalized_email = str(value).lower()
        else:
            setattr(row, key, value)
    uow.session.add(row)
    uow.session.flush()
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "contact.updated" if identifier else "contact.created",
        "contact",
        row.id,
        list(changes),
        request.state.request_id,
    )
    return repository.contact_view(uow.session, row)


def archive(
    uow: UnitOfWork,
    identifier: UUID,
    payload: ArchiveInput,
    request: Request,
    is_contact: bool = False,
) -> CustomerView | ContactView:
    require_role(uow.scope, "admin", "manager")
    row = (
        repository.contact(uow.session, identifier, True)
        if is_contact
        else repository.customer(uow.session, identifier, True)
    )
    match_version(request, row.version)
    if row.archived_at:
        raise Fault(409, "archived", "This record is already archived.")
    from app.modules.cases.assignments import check_archive

    check_archive(uow, identifier, is_contact)
    row.archived_at = now()
    row.updated_at = now()
    row.version += 1
    contact_ids = select(Contact.id).where(
        Contact.id == identifier if is_contact else Contact.customer_id == identifier
    )
    binding_ids = select(PortalBinding.id).where(PortalBinding.contact_id.in_(contact_ids))
    uow.session.execute(
        update(SetupToken)
        .where(SetupToken.portal_binding_id.in_(binding_ids), SetupToken.used_at.is_(None))
        .values(used_at=now())
    )
    uow.session.execute(
        update(PortalBinding)
        .where(PortalBinding.contact_id.in_(contact_ids))
        .values(active=False, version=PortalBinding.version + 1, updated_at=now())
    )
    record_audit(
        uow.session,
        uow.scope.workspace_id,
        uow.scope.user_id,
        "contact.archived" if is_contact else "customer.archived",
        "contact" if is_contact else "customer",
        identifier,
        ["archived_at"],
        request.state.request_id,
        payload.reason,
    )
    uow.session.flush()
    return (
        repository.contact_view(uow.session, row)
        if isinstance(row, Contact)
        else repository.customer_view(uow.session, row)
    )
