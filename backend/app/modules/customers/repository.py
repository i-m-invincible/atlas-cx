from datetime import datetime
from uuid import UUID

from sqlalchemy import literal, select, tuple_
from sqlalchemy.orm import Session

from app.modules.customers.models import Contact, Customer
from app.modules.customers.schemas import ContactFilters, ContactView, CustomerFilters, CustomerView
from app.modules.identity.models import Membership, PortalBinding, User
from app.platform.protocol import Fault, missing, read_cursor, sign_cursor


def customer(session: Session, identifier: UUID, lock: bool = False) -> Customer:
    value = session.get(Customer, identifier, with_for_update=lock)
    if value is None:
        raise missing()
    return value


def contact(session: Session, identifier: UUID, lock: bool = False) -> Contact:
    value = session.get(Contact, identifier, with_for_update=lock)
    if value is None:
        raise missing()
    return value


def customer_view(session: Session, row: Customer) -> CustomerView:
    owner = (
        session.scalar(
            select(User.display_name)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.id == row.owner_member_id)
        )
        if row.owner_member_id
        else None
    )
    return CustomerView(
        **{
            field: getattr(row, field) for field in CustomerView.model_fields if hasattr(row, field)
        },
        owner_name=owner,
    )


def contact_view(session: Session, row: Contact) -> ContactView:
    active = session.scalar(select(PortalBinding.active).where(PortalBinding.contact_id == row.id))
    return ContactView(
        id=row.id,
        customer_id=row.customer_id,
        version=row.version,
        name=row.name,
        email=row.normalized_email,
        phone=row.phone,
        archived_at=row.archived_at,
        portal_enabled=bool(active),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def page_customers(
    session: Session, workspace_id: UUID, filters: CustomerFilters
) -> tuple[list[CustomerView], str | None]:
    binding = {
        "workspace": str(workspace_id),
        "resource": "customers",
        **filters.model_dump(mode="json", exclude={"cursor", "limit"}),
    }
    query = select(Customer).where(
        Customer.archived_at.is_not(None) if filters.archived else Customer.archived_at.is_(None)
    )
    if filters.q:
        pattern = (
            "%" + filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        query = query.where(Customer.name.ilike(pattern) | Customer.external_id.ilike(pattern))
    if filters.lifecycle:
        query = query.where(Customer.lifecycle.in_(filters.lifecycle.split(",")))
    if filters.owner_id:
        query = query.where(Customer.owner_member_id == filters.owner_id)
    if filters.tag:
        query = query.where(Customer.tags.contains([filters.tag]))
    if filters.cursor:
        parts = read_cursor(filters.cursor, binding)
        try:
            value, identifier = parts
            boundary_id = UUID(identifier)
            if filters.sort == "name":
                query = query.where(
                    tuple_(Customer.name, Customer.id)
                    > tuple_(literal(value), literal(boundary_id))
                )
            else:
                query = query.where(
                    tuple_(Customer.created_at, Customer.id)
                    < tuple_(literal(datetime.fromisoformat(value)), literal(boundary_id))
                )
        except (ValueError, TypeError):
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    query = (
        query.order_by(Customer.name, Customer.id)
        if filters.sort == "name"
        else query.order_by(Customer.created_at.desc(), Customer.id.desc())
    )
    rows = list(session.scalars(query.limit(filters.limit + 1)))
    more = len(rows) > filters.limit
    rows = rows[: filters.limit]
    cursor = (
        sign_cursor(
            binding,
            [
                rows[-1].name if filters.sort == "name" else rows[-1].created_at.isoformat(),
                str(rows[-1].id),
            ],
        )
        if more
        else None
    )
    return [customer_view(session, row) for row in rows], cursor


def page_contacts(
    session: Session, workspace_id: UUID, filters: ContactFilters
) -> tuple[list[ContactView], str | None]:
    binding = {
        "workspace": str(workspace_id),
        "resource": "contacts",
        **filters.model_dump(mode="json", exclude={"cursor", "limit"}),
    }
    query = select(Contact)
    if filters.customer_id:
        customer(session, filters.customer_id)
        query = query.where(Contact.customer_id == filters.customer_id)
    if filters.q:
        pattern = (
            "%" + filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        query = query.where(Contact.name.ilike(pattern) | Contact.normalized_email.ilike(pattern))
    if filters.cursor:
        try:
            value, identifier = read_cursor(filters.cursor, binding)
            query = query.where(
                tuple_(Contact.created_at, Contact.id)
                < tuple_(literal(datetime.fromisoformat(value)), literal(UUID(identifier)))
            )
        except (ValueError, TypeError):
            raise Fault(400, "invalid_cursor", "Return to the first page.") from None
    rows = list(
        session.scalars(
            query.order_by(Contact.created_at.desc(), Contact.id.desc()).limit(filters.limit + 1)
        )
    )
    more = len(rows) > filters.limit
    rows = rows[: filters.limit]
    cursor = (
        sign_cursor(binding, [rows[-1].created_at.isoformat(), str(rows[-1].id)]) if more else None
    )
    return [contact_view(session, row) for row in rows], cursor
