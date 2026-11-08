"""Case responsibilities checked by customer/workspace administration."""

from uuid import UUID

from fastapi import Request
from sqlalchemy import select

from app.modules.cases.models import Case
from app.modules.cases.service import audit, instant_for, validate_assignment
from app.platform.auth import UnitOfWork
from app.platform.protocol import Fault

ACTIVE = ("new", "open", "pending_customer")


def has_work(uow: UnitOfWork, member_id: UUID) -> bool:
    return (
        uow.session.scalar(
            select(Case.id)
            .where(Case.assignee_member_id == member_id, Case.state.in_(ACTIVE))
            .limit(1)
        )
        is not None
    )


def transfer(uow: UnitOfWork, member_id: UUID, replacement_id: UUID, request: Request) -> None:
    rows = list(
        uow.session.scalars(
            select(Case)
            .where(Case.assignee_member_id == member_id, Case.state.in_(ACTIVE))
            .with_for_update()
        )
    )
    conflicts = []
    for row in rows:
        try:
            validate_assignment(uow, replacement_id, row.team_id, True)
        except Fault:
            conflicts.append(f"CX-{row.number:06d}")
    if conflicts:
        raise Fault(
            409,
            "case_assignment_conflicts",
            "The replacement cannot handle these cases: "
            + ", ".join(conflicts)
            + ". Adjust team membership or transfer the cases first.",
        )
    for row in rows:
        row.assignee_member_id = replacement_id
        row.version += 1
        row.updated_at = instant_for(row)
        audit(uow, row, request, "case.assignee_reassigned", ["assignee_member_id"])


def check_team(
    uow: UnitOfWork, team_id: UUID, member_ids: list[UUID] | None, archived: bool | None
) -> None:
    rows = list(
        uow.session.scalars(select(Case).where(Case.team_id == team_id, Case.state.in_(ACTIVE)))
    )
    conflicts = [
        row
        for row in rows
        if archived
        or (
            member_ids is not None
            and row.assignee_member_id is not None
            and row.assignee_member_id not in member_ids
        )
    ]
    if conflicts:
        raise Fault(
            409,
            "case_assignment_conflicts",
            "Move these active cases before changing this team: "
            + ", ".join(f"CX-{row.number:06d}" for row in conflicts)
            + ".",
        )


def check_archive(uow: UnitOfWork, identifier: UUID, is_contact: bool = False) -> None:
    column = Case.requester_contact_id if is_contact else Case.customer_id
    if uow.session.scalar(
        select(Case.id).where(column == identifier, Case.state.in_(ACTIVE)).limit(1)
    ):
        raise Fault(
            409, "active_cases", "Resolve or close active cases before archiving this record."
        )
