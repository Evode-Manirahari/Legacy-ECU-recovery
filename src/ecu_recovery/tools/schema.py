"""A small JSON Schema subset, validated by hand.

The repository carries no mandatory runtime dependency, which is a recorded
architectural property, and `pyproject.toml` is outside this node's ownership.
So rather than pulling in a validator, this module implements the subset the
tool contracts actually use, in the same spirit as the graph's YAML loader.

The parser is strict on purpose. An unknown argument is an error, never a
silently ignored key: an agent that misspells `offset` must be told, not handed
page one forever while believing it paged. Anything outside the supported subset
raises at schema-definition time rather than passing validation by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SUPPORTED_TYPES = ("object", "array", "string", "integer", "boolean")


class SchemaError(ValueError):
    """A schema itself is malformed. A programming error, not a caller error."""


@dataclass(frozen=True)
class ValidationFailure:
    """Why one argument was refused, and which one it was."""

    field: str
    message: str


def _check_schema(schema: dict[str, Any], path: str = "") -> None:
    kind = schema.get("type")
    if kind not in SUPPORTED_TYPES:
        raise SchemaError(f"{path or 'schema'}: unsupported type {kind!r}")
    if kind == "object":
        for name, child in schema.get("properties", {}).items():
            _check_schema(child, f"{path}.{name}" if path else name)
        unknown = set(schema.get("required", ())) - set(schema.get("properties", {}))
        if unknown:
            raise SchemaError(f"{path or 'schema'}: required names not in properties: {unknown}")
    if kind == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            raise SchemaError(f"{path or 'schema'}: array schema needs an items schema")
        _check_schema(items, f"{path}[]")


def validate_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Reject a malformed schema when it is defined, not when it is first used."""
    _check_schema(schema)
    return schema


def _validate_value(
    value: Any, schema: dict[str, Any], field: str
) -> tuple[Any, ValidationFailure | None]:
    kind = schema["type"]
    if kind == "integer":
        # bool is an int in Python; an agent passing true for a limit is a
        # mistake worth naming rather than coercing to 1.
        if isinstance(value, bool) or not isinstance(value, int):
            return None, ValidationFailure(
                field, f"expected an integer, got {type(value).__name__}"
            )
        minimum, maximum = schema.get("minimum"), schema.get("maximum")
        if minimum is not None and value < minimum:
            return None, ValidationFailure(field, f"must be >= {minimum}, got {value}")
        if maximum is not None and value > maximum:
            return None, ValidationFailure(field, f"must be <= {maximum}, got {value}")
        return value, None
    if kind == "string":
        if not isinstance(value, str):
            return None, ValidationFailure(field, f"expected a string, got {type(value).__name__}")
        choices = schema.get("enum")
        if choices is not None and value not in choices:
            return None, ValidationFailure(
                field, f"must be one of {sorted(choices)}, got {value!r}"
            )
        if len(value) > int(schema.get("maxLength", 4096)):
            return None, ValidationFailure(field, "is longer than the schema allows")
        if not value and schema.get("minLength", 0) > 0:
            return None, ValidationFailure(field, "must not be empty")
        return value, None
    if kind == "boolean":
        if not isinstance(value, bool):
            return None, ValidationFailure(field, f"expected a boolean, got {type(value).__name__}")
        return value, None
    if kind == "array":
        if not isinstance(value, list):
            return None, ValidationFailure(field, f"expected an array, got {type(value).__name__}")
        maximum = schema.get("maxItems")
        if maximum is not None and len(value) > int(maximum):
            return None, ValidationFailure(field, f"holds more than {maximum} items")
        items: list[Any] = []
        for index, item in enumerate(value):
            converted, failure = _validate_value(item, schema["items"], f"{field}[{index}]")
            if failure is not None:
                return None, failure
            items.append(converted)
        return items, None
    if kind == "object":
        if not schema.get("properties"):
            # A record whose shape belongs to the analysis layer. Check that it
            # is an object and pass it through: re-declaring every analysis
            # field here would be a second copy to keep in step with the first.
            if not isinstance(value, dict):
                return None, ValidationFailure(field, "expected an object")
            return value, None
        return validate(value, schema, field)
    return None, ValidationFailure(field, f"unsupported type {kind!r}")


def validate(
    payload: Any, schema: dict[str, Any], path: str = ""
) -> tuple[dict[str, Any] | None, ValidationFailure | None]:
    """Check a payload against an object schema and fill in defaults.

    Returns the normalized arguments, or the first failure. One failure at a
    time is deliberate: a caller fixes them one at a time anyway, and naming the
    first keeps the error unambiguous.
    """
    if not isinstance(payload, dict):
        return None, ValidationFailure(path or "arguments", "expected an object")
    properties: dict[str, Any] = schema.get("properties", {})

    unknown = sorted(set(payload) - set(properties))
    if unknown and not schema.get("additionalProperties", False):
        return None, ValidationFailure(
            unknown[0], f"is not an argument of this tool; expected {sorted(properties)}"
        )

    # With additional properties allowed, unknown keys are carried through
    # rather than dropped. Output validation must never quietly delete the data
    # it was asked to check.
    result: dict[str, Any] = dict(payload) if schema.get("additionalProperties", False) else {}
    for name in schema.get("required", ()):
        if name not in payload:
            return None, ValidationFailure(name, "is required")

    for name, child in properties.items():
        qualified = f"{path}.{name}" if path else name
        if name not in payload:
            if "default" in child:
                result[name] = child["default"]
            continue
        value, failure = _validate_value(payload[name], child, qualified)
        if failure is not None:
            return None, failure
        result[name] = value
    return result, None
