import pytest

from app.modules.cases.schemas import FieldDefinition, valid_field_value
from app.modules.customers.import_service import MAX_BYTES, parse_csv
from app.modules.workspace.case_config_service import validate_fields
from app.modules.workspace.case_configuration import default_definition
from app.modules.workspace.case_presets import starter_presets
from app.platform.protocol import Fault


@pytest.mark.parametrize(
    ("kind", "valid", "invalid"),
    [
        ("string", "Reference", " "),
        ("integer", 2, True),
        ("decimal", 2.5, "2.5"),
        ("boolean", False, 0),
        ("date", "2026-11-09", "2026-11-09T00:00:00Z"),
        ("single_select", "yes", "unknown"),
    ],
)
def test_defaults_and_case_values_share_type_rules(
    kind: str, valid: object, invalid: object
) -> None:
    field = FieldDefinition.model_validate(
        {
            "key": "reference",
            "label": "Reference",
            "type": kind,
            "allowed_values": ["yes", "no"] if kind == "single_select" else [],
        }
    )
    assert valid_field_value(field, valid)
    assert not valid_field_value(field, invalid)


def test_presets_are_distinct_valid_independent_definitions() -> None:
    presets = starter_presets()
    assert [row.label for row in presets] == [
        "SaaS",
        "Service business",
        "E-commerce",
        "Education",
        "Subscription business",
    ]
    assert (
        len({tuple(category.key for category in row.definition.categories) for row in presets}) == 5
    )
    for row in presets:
        validate_fields(row.definition)
        assert row.definition.priorities == default_definition().priorities
        assert row.definition.fields
    presets[1].definition.categories[0].label = "Changed"
    assert starter_presets()[1].definition.categories[0].label == "Appointment"


@pytest.mark.parametrize(
    "change",
    [
        {"required_on_create": True},
        {"portal_editable_on_create": True},
        {"type": "integer", "minimum": 3, "maximum": 2},
        {"type": "integer", "minimum": 3, "default": 2},
        {"type": "single_select", "allowed_values": ["same", "same"]},
        {"type": "date", "default": "2026-02-30"},
    ],
)
def test_publication_rejects_unsafe_fields(change: dict[str, object]) -> None:
    definition = default_definition()
    definition.fields = [
        FieldDefinition.model_validate(
            {
                "key": "reference",
                "label": "Reference",
                "type": "string",
                **change,
            }
        )
    ]
    with pytest.raises(Fault) as error:
        validate_fields(definition)
    assert error.value.status == 422


@pytest.mark.parametrize(
    ("contents", "status"),
    [
        (b"external_id,kind\nX,business\n", 422),
        (b"external_id,name,kind,kind\n", 422),
        (b"external_id,name,kind\nX,\xff,business\n", 415),
        (b"a" * (MAX_BYTES + 1), 413),
        (b"external_id,name,kind\n" + b"X,Name,business\n" * 1001, 413),
    ],
)
def test_csv_rejects_malformed_or_oversized_input(contents: bytes, status: int) -> None:
    with pytest.raises(Fault) as error:
        parse_csv(contents)
    assert error.value.status == status


def test_csv_handles_quoted_newlines_and_reports_physical_row_number() -> None:
    rows = parse_csv(
        b'\xef\xbb\xbfexternal_id,name,kind\r\nX,"Line 1\nLine 2",business\r\nY,Next,person\r\n'
    )
    assert [(row.row, row.cells["name"]) for row in rows] == [(2, "Line 1\nLine 2"), (4, "Next")]
