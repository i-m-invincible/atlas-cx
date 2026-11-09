import csv
import hashlib
import io
from collections import Counter
from datetime import timedelta
from typing import cast
from uuid import UUID

from fastapi import Request
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.modules.customers.import_models import CustomerImport
from app.modules.customers.import_schemas import (
    CsvRow,
    ImportRow,
    ImportStatus,
    ImportView,
    RowIssue,
)
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import persist_customer
from app.modules.identity.models import Membership, User
from app.platform import idempotency
from app.platform.audit import record_audit
from app.platform.auth import UnitOfWork, require_role
from app.platform.protocol import Fault, Input, match_version, missing, now

MAX_BYTES = 1024 * 1024
MAX_ROWS = 1000
REQUIRED = {"external_id", "name", "kind"}
COLUMNS = REQUIRED | {"lifecycle", "owner_email", "tags", "activity_expected"}


def parse_csv(contents: bytes) -> list[CsvRow]:
    if len(contents) > MAX_BYTES:
        raise Fault(413, "csv_too_large", "Choose a CSV file no larger than 1 MiB.")
    try:
        document = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Fault(415, "invalid_csv_encoding", "Save the CSV as UTF-8 and try again.") from None
    if "\x00" in document:
        raise Fault(422, "invalid_csv", "Remove null characters from the CSV.")
    records = csv.reader(io.StringIO(document, newline=""), strict=True)
    try:
        header = [name.strip() for name in next(records, [])]
        if not set(header) >= REQUIRED or set(header) - COLUMNS or len(set(header)) != len(header):
            raise Fault(
                422,
                "invalid_csv_header",
                "Use unique supported columns including external_id, name, and kind.",
            )
        rows: list[CsvRow] = []
        while True:
            number = records.line_num + 1
            record = next(records, None)
            if record is None:
                break
            if not record:
                continue
            if len(rows) == MAX_ROWS:
                raise Fault(413, "too_many_rows", "Choose a CSV with at most 1,000 data rows.")
            cells = {name: value.strip() for name, value in zip(header, record, strict=False)}
            if len(record) != len(header):
                cells["__row_error__"] = "Use the same number of cells as the header."
            rows.append(CsvRow(row=number, cells=cells))
    except csv.Error:
        raise Fault(422, "invalid_csv", "Review the CSV quoting and cell sizes.") from None
    if not rows:
        raise Fault(422, "empty_csv", "Include at least one customer row.")
    return rows


def plan(uow: UnitOfWork, rows: list[CsvRow]) -> list[ImportRow]:
    identifiers = Counter(row.cells.get("external_id", "") for row in rows)
    customers = {
        row.external_id: row
        for row in uow.session.scalars(
            select(Customer).where(Customer.external_id.in_(list(identifiers)))
        )
    }
    emails = {row.cells["owner_email"].lower() for row in rows if row.cells.get("owner_email")}
    owners = {
        email: identifier
        for email, identifier in uow.session.execute(
            select(User.normalized_email, Membership.id)
            .join(Membership, Membership.user_id == User.id)
            .where(
                User.normalized_email.in_(emails),
                Membership.active.is_(True),
                Membership.role.in_(("admin", "manager", "agent")),
            )
        )
    }
    return [
        plan_row(row, customers.get(row.cells.get("external_id", "")), identifiers, owners)
        for row in rows
    ]


def plan_row(
    row: CsvRow, customer: Customer | None, identifiers: Counter[str], owners: dict[str, UUID]
) -> ImportRow:
    cells = row.cells
    errors = []
    if "__row_error__" in cells:
        errors.append(RowIssue(field="row", message=cells["__row_error__"]))
    external_id = cells.get("external_id", "")
    if not external_id:
        errors.append(RowIssue(field="external_id", message="Enter an external ID."))
    if external_id and identifiers[external_id] > 1:
        errors.append(
            RowIssue(
                field="external_id", message="This external ID appears more than once in the file."
            )
        )
    values: dict[str, object] = {name: cells.get(name, "") for name in REQUIRED}
    if customer and customer.archived_at:
        errors.append(RowIssue(field="external_id", message="This customer is archived."))
    if customer and cells.get("kind") != customer.kind:
        errors.append(RowIssue(field="kind", message="An existing customer's kind cannot change."))
    if cells.get("lifecycle"):
        values["lifecycle"] = cells["lifecycle"]
    if cells.get("owner_email"):
        owner = owners.get(cells["owner_email"].lower())
        if not owner:
            errors.append(
                RowIssue(field="owner_email", message="Choose an active workspace owner by email.")
            )
        else:
            values["owner_member_id"] = owner
    if cells.get("tags"):
        values["tags"] = cells["tags"].split(";")
    if cells.get("activity_expected"):
        activity = cells["activity_expected"].lower()
        if activity not in {"true", "false"}:
            errors.append(RowIssue(field="activity_expected", message="Enter true or false."))
        else:
            values["activity_expected"] = activity == "true"
    normalized = {}
    try:
        validated = CustomerCreate.model_validate(values)
        normalized = validated.model_dump(mode="json", exclude_unset=customer is not None)
    except ValidationError as exc:
        errors.extend(
            RowIssue(field=str(error["loc"][0]), message="Review this customer value.")
            for error in exc.errors()
        )
    return ImportRow(
        row=row.row,
        action="error" if errors else "update" if customer else "create",
        values=normalized,
        errors=errors,
        customer_id=customer.id if customer else None,
        customer_version=customer.version if customer else None,
    )


def purge_expired(uow: UnitOfWork) -> None:
    instant = now()
    uow.session.execute(
        update(CustomerImport)
        .where(
            CustomerImport.expires_at <= instant,
            (CustomerImport.status == "validated") | (CustomerImport.row_results_json != []),
        )
        .values(
            normalized_rows_json=[],
            row_results_json=[],
            version=CustomerImport.version + 1,
            updated_at=instant,
        )
    )
    uow.session.execute(
        update(CustomerImport)
        .where(CustomerImport.expires_at <= instant, CustomerImport.status == "validated")
        .values(status="expired", updated_at=instant)
    )


def audit(uow: UnitOfWork, row: CustomerImport, action: str, request: Request) -> None:
    record_audit(
        uow.session,
        row.workspace_id,
        uow.scope.user_id,
        action,
        "customer_import",
        row.id,
        ["status", "create_count", "update_count", "error_count"],
        request.state.request_id,
    )


def stage(uow: UnitOfWork, contents: bytes, request: Request) -> CustomerImport:
    require_role(uow.scope, "admin", "manager")
    rows = parse_csv(contents)
    preview = plan(uow, rows)
    assert uow.scope.member_id
    purge_expired(uow)
    row = CustomerImport(
        workspace_id=uow.scope.workspace_id,
        submitted_by_member_id=uow.scope.member_id,
        input_hash=hashlib.sha256(contents).hexdigest(),
        normalized_rows_json=[item.model_dump(mode="json") for item in rows],
        row_results_json=[item.model_dump(mode="json") for item in preview],
        create_count=sum(item.action == "create" for item in preview),
        update_count=sum(item.action == "update" for item in preview),
        error_count=sum(item.action == "error" for item in preview),
        expires_at=now() + timedelta(hours=24),
    )
    uow.session.add(row)
    uow.session.flush()
    audit(uow, row, "customer_import.validated", request)
    return row


def get(uow: UnitOfWork, identifier: UUID, lock: bool = False) -> CustomerImport:
    row = uow.session.get(CustomerImport, identifier, with_for_update=lock)
    if not row or (
        uow.scope.member_id != row.submitted_by_member_id
        and uow.scope.role not in {"admin", "manager"}
    ):
        raise missing()
    return row


def view(row: CustomerImport) -> ImportView:
    expired = row.expires_at <= now()
    return ImportView(
        id=row.id,
        version=row.version,
        status="expired"
        if expired and row.status == "validated"
        else cast(ImportStatus, row.status),
        create_count=row.create_count,
        update_count=row.update_count,
        error_count=row.error_count,
        rows=[] if expired else [ImportRow.model_validate(item) for item in row.row_results_json],
        expires_at=row.expires_at,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


def commit(
    uow: UnitOfWork, identifier: UUID, request: Request
) -> tuple[CustomerImport, Fault | None]:
    require_role(uow.scope, "admin", "manager")
    purge_expired(uow)
    row = get(uow, identifier, True)
    replay, exists = idempotency.prepare(uow, request, Input())
    if exists:
        return row, None
    if row.status == "expired":
        raise Fault(409, "import_expired", "The preview expired. Validate the CSV again.")
    if row.status != "validated":
        raise Fault(409, "import_not_pending", "This import can no longer be committed.")
    match_version(request, row.version)
    if row.error_count:
        raise Fault(409, "import_invalid", "Fix the rows listed below before importing.")
    rows = [CsvRow.model_validate(item) for item in row.normalized_rows_json]
    confirmed = plan(uow, rows)
    try:
        if [item.model_dump(mode="json") for item in confirmed] != row.row_results_json:
            raise Fault(409, "import_changed", "Customer data changed. Validate the CSV again.")
        with uow.session.begin_nested():
            for item in confirmed:
                payload = CustomerCreate.model_validate(item.values)
                target = (
                    uow.session.get(Customer, item.customer_id, with_for_update=True)
                    if item.customer_id
                    else None
                )
                if item.customer_id and (not target or target.version != item.customer_version):
                    raise Fault(
                        409, "import_changed", "Customer data changed. Validate the CSV again."
                    )
                changes = payload.model_dump(exclude_unset=target is not None)
                if target:
                    del changes["kind"]
                    del changes["external_id"]
                customer = persist_customer(uow, changes, request, target)
                item.customer_id = customer.id
                item.customer_version = customer.version
    except (Fault, IntegrityError):
        row.status = "failed"
        row.version += 1
        row.updated_at = now()
        # An unsuccessful commit must not leave a successful replay entry.
        if replay in uow.session.new:
            uow.session.expunge(replay)
        else:
            replay.expires_at = row.updated_at
        audit(uow, row, "customer_import.failed", request)
        return row, Fault(409, "import_changed", "Customer data changed. Validate the CSV again.")
    row.status = "committed"
    row.row_results_json = [item.model_dump(mode="json") for item in confirmed]
    row.normalized_rows_json = []
    row.completed_at = row.updated_at = now()
    row.version += 1
    audit(uow, row, "customer_import.committed", request)
    idempotency.complete(replay, "customer_import", row.id)
    return row, None
