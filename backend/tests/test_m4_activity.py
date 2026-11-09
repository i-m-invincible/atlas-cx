from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.modules.activities.schemas import EventInput, PropertyRule
from app.modules.activities.service import event_hash, validate_properties
from app.modules.analytics.service import boundary, csv_cell, rate
from app.platform.protocol import Fault


def test_canonical_hash_orders_properties_and_normalizes_the_instant() -> None:
    common = {"event_name": "sample", "external_event_id": "one", "customer_external_id": "alpha"}
    first = EventInput(
        **common, occurred_at="2026-04-10T12:00:00Z", properties={"n": 1, "s": " a "}
    )
    second = EventInput(
        **common, occurred_at="2026-04-10T08:00:00-04:00", properties={"s": " a ", "n": 1}
    )
    assert event_hash(first) == event_hash(second)
    assert event_hash(first) != event_hash(
        first.model_copy(update={"properties": {"n": 1, "s": "a"}})
    )


@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_integer_property_does_not_coerce_values(value: object) -> None:
    event = EventInput.model_validate(
        {
            "event_name": "sample",
            "external_event_id": "one",
            "customer_external_id": "alpha",
            "occurred_at": "2026-04-10T12:00:00Z",
            "properties": {"n": value},
        }
    )
    with pytest.raises(Fault, match="invalid_property"):
        validate_properties(event, {"n": PropertyRule(type="integer")})


@pytest.mark.parametrize("value", ["2026-04-10T12:00:00", 1])
def test_ingestion_requires_an_explicit_offset(value: object) -> None:
    with pytest.raises(ValidationError):
        EventInput.model_validate(
            {
                "event_name": "sample",
                "external_event_id": "one",
                "customer_external_id": "alpha",
                "occurred_at": value,
            }
        )


def test_local_date_boundaries_follow_daylight_saving() -> None:
    zone = ZoneInfo("America/New_York")
    assert boundary("2026-03-08", date.min, zone).astimezone(UTC) == datetime(
        2026, 3, 8, 5, tzinfo=UTC
    )
    assert boundary("2026-03-09", date.min, zone).astimezone(UTC) == datetime(
        2026, 3, 9, 4, tzinfo=UTC
    )
    assert rate(0, 0).share is None


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-1", "@sum", "\tword", "\rword", "  =1"])
def test_export_neutralizes_formula_cells(value: str) -> None:
    assert csv_cell(value) == "'" + value
