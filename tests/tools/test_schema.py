"""The hand-written schema subset.

Validation is the tool layer's whole defence against a malformed call, so it is
tested on its own rather than only through the tools.
"""

from __future__ import annotations

from typing import Any

import pytest

from ecu_recovery.tools.schema import SchemaError, validate, validate_schema

OBJECT = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
        "name": {"type": "string", "maxLength": 8},
        "flag": {"type": "boolean", "default": False},
    },
    "required": ["name"],
}


def test_defaults_fill_in_for_omitted_arguments() -> None:
    parsed, failure = validate({"name": "x"}, OBJECT)

    assert failure is None
    assert parsed == {"limit": 10, "name": "x", "flag": False}


def test_a_missing_required_argument_names_itself() -> None:
    parsed, failure = validate({}, OBJECT)

    assert parsed is None
    assert failure is not None
    assert failure.field == "name"
    assert "required" in failure.message


def test_an_unknown_argument_is_refused_rather_than_ignored() -> None:
    """Silently dropping a typo would let a caller page forever at offset zero."""
    parsed, failure = validate({"name": "x", "limt": 5}, OBJECT)

    assert parsed is None
    assert failure is not None
    assert failure.field == "limt"


@pytest.mark.parametrize(
    "value,expected_field",
    [({"name": "x", "limit": 0}, "limit"), ({"name": "x", "limit": 101}, "limit")],
)
def test_integer_bounds_are_enforced(value: dict[str, Any], expected_field: str) -> None:
    _, failure = validate(value, OBJECT)

    assert failure is not None
    assert failure.field == expected_field


def test_a_boolean_is_not_an_integer() -> None:
    """True would otherwise pass as 1 and quietly become a limit."""
    _, failure = validate({"name": "x", "limit": True}, OBJECT)

    assert failure is not None
    assert "integer" in failure.message


def test_a_string_longer_than_the_schema_allows_is_refused() -> None:
    _, failure = validate({"name": "x" * 9}, OBJECT)

    assert failure is not None
    assert failure.field == "name"


def test_an_enum_lists_what_it_would_have_accepted() -> None:
    schema = {"type": "object", "properties": {"mode": {"type": "string", "enum": ["a", "b"]}}}

    _, failure = validate({"mode": "c"}, schema)

    assert failure is not None
    assert "'a', 'b'" in failure.message.replace('"', "'")


def test_arrays_validate_their_items_and_report_the_index() -> None:
    schema = {
        "type": "object",
        "properties": {"values": {"type": "array", "items": {"type": "integer", "minimum": 0}}},
    }

    _, failure = validate({"values": [1, -2]}, schema)

    assert failure is not None
    assert failure.field == "values[1]"


def test_a_record_shaped_object_passes_through_unchanged() -> None:
    """Output schemas describe records they do not own; checking must not rebuild them."""
    schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {"type": "object"}}},
    }

    parsed, failure = validate({"items": [{"address": "0x1", "name": "f"}]}, schema)

    assert failure is None
    assert parsed == {"items": [{"address": "0x1", "name": "f"}]}


def test_a_non_object_payload_is_refused() -> None:
    _, failure = validate([1, 2, 3], OBJECT)

    assert failure is not None


def test_a_malformed_schema_is_caught_when_it_is_defined() -> None:
    with pytest.raises(SchemaError, match="unsupported type"):
        validate_schema({"type": "number"})


def test_a_required_name_absent_from_properties_is_a_schema_bug() -> None:
    with pytest.raises(SchemaError, match="required names"):
        validate_schema({"type": "object", "properties": {}, "required": ["ghost"]})


def test_an_array_schema_without_items_is_a_schema_bug() -> None:
    with pytest.raises(SchemaError, match="items schema"):
        validate_schema({"type": "object", "properties": {"a": {"type": "array"}}})
