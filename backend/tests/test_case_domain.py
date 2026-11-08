from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.modules.cases.clocks import clock
from app.modules.cases.schemas import CaseCreatePortal, Definition, TransitionInput
from app.modules.cases.service import values_for
from app.modules.workspace.case_configuration import default_definition, public_config
from app.platform.protocol import Fault

START = datetime(2026, 11, 8, 9, tzinfo=UTC)


def test_independent_pause_resolution_fixture() -> None:
    result = clock(
        START,
        START + timedelta(hours=4),
        7200,
        7200,
        finished_at=START + timedelta(hours=3, minutes=45),
    )
    assert result.elapsed_seconds == 6300
    assert result.remaining_seconds == 900
    assert result.status == "met" and not result.is_overdue
    # Reopening does not mutate the first cycle's measured duration.
    reopened = clock(START + timedelta(hours=5), START + timedelta(hours=5, minutes=30), 7200)
    assert reopened.elapsed_seconds == 1800 and result.elapsed_seconds == 6300


@pytest.mark.parametrize("seconds,overdue", [(7199, False), (7200, False), (7201, True)])
def test_target_boundary_is_strict(seconds: int, overdue: bool) -> None:
    result = clock(START, START + timedelta(seconds=seconds), 7200)
    assert result.is_overdue is overdue
    assert result.status == ("overdue" if overdue else "due")


def test_paused_clock_reports_remaining_active_time() -> None:
    result = clock(
        START, START + timedelta(hours=5), 7200, pause_started_at=START + timedelta(hours=1)
    )
    assert result.status == "paused" and result.due_at is None
    assert result.elapsed_seconds == 3600 and result.remaining_seconds == 3600
    overdue = clock(
        START, START + timedelta(hours=5), 7200, pause_started_at=START + timedelta(hours=3)
    )
    assert overdue.status == "paused" and overdue.is_overdue


@pytest.mark.parametrize(
    "elapsed,paused,pause",
    [
        (-1, 0, None),
        (1, -1, None),
        (1, 2, None),
        (1, 0, START - timedelta(seconds=1)),
        (1, 0, START + timedelta(seconds=2)),
    ],
)
def test_invalid_clock_data_is_not_hidden(
    elapsed: int, paused: int, pause: datetime | None
) -> None:
    with pytest.raises(ValueError):
        clock(START, START + timedelta(seconds=elapsed), 7200, paused, pause)


def test_first_response_clock_never_pauses() -> None:
    result = clock(START, START + timedelta(hours=12), 3600, finished_at=START + timedelta(hours=2))
    assert result.elapsed_seconds == 7200 and result.status == "missed"


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "resolve"},
        {"action": "resolve", "resolution_summary": "", "resolution_code": "fixed"},
        {"action": "ask_customer"},
        {"action": "resume"},
        {"action": "close"},
        {"action": "reopen"},
        {"action": "triage", "reason": "Unrelated field"},
        {"action": "resolve", "resolution_summary": "Resolved", "resolution_code": "invented"},
    ],
)
def test_action_specific_inputs_are_required(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        TransitionInput.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    ["customer_id", "requester_contact_id", "state", "priority", "assignee_member_id", "source"],
)
def test_portal_cannot_supply_staff_or_server_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        CaseCreatePortal.model_validate(
            {
                "category_key": "access",
                "subject": "Access issue",
                "description": "Synthetic request",
                field: "forged",
            }
        )


def test_default_configuration_and_portal_projection() -> None:
    definition = default_definition()
    assert definition.priorities["urgent"].response_minutes == 60
    assert definition.priorities["low"].resolution_minutes == 5760
    projection = public_config(definition).model_dump()
    assert "priorities" not in projection and "default_team_id" not in str(projection)
    assert projection["state_labels"]["pending_customer"] == "Awaiting customer"


def field_config() -> Definition:
    data = default_definition().model_dump()
    data["fields"] = [
        {
            "key": "reference",
            "label": "Reference",
            "type": "string",
            "required_on_resolve": True,
            "portal_visible": True,
            "portal_editable_on_create": True,
        },
        {"key": "quantity", "label": "Quantity", "type": "integer", "minimum": 1, "maximum": 5},
        {"key": "internal", "label": "Internal review", "type": "boolean", "default": False},
    ]
    return Definition.model_validate(data)


def test_required_resolution_fields_and_hidden_creation_defaults() -> None:
    definition = field_config()
    created = values_for(definition, {}, portal=True)
    assert created["internal"] is False and created["reference"] is None
    with pytest.raises(Fault, match="Reference"):
        values_for(definition, {}, existing=created, resolving=True)
    assert (
        values_for(definition, {"reference": "Confirmed"}, existing=created, resolving=True)[
            "reference"
        ]
        == "Confirmed"
    )
    public = public_config(definition).model_dump()
    assert "internal" not in str(public) and "Internal review" not in str(public)


@pytest.mark.parametrize(
    "values,portal",
    [
        ({"unknown": "value"}, False),
        ({"quantity": True}, False),
        ({"quantity": 9}, False),
        ({"internal": True}, True),
    ],
)
def test_custom_values_cannot_bypass_types_or_visibility(values: dict, portal: bool) -> None:
    with pytest.raises(Fault):
        values_for(field_config(), values, portal=portal)
