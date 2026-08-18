"""What a tool is, and what a tool call returns.

Every tool answers with a `ToolResult`, never an exception. An agent cannot
catch a Python traceback, and a stack trace is not a fact it can reason about;
a typed code and a sentence it can act on are. That is why failure is a value
here rather than control flow.

Nothing in this module knows what Ghidra is.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .schema import validate_schema

#: Error codes are the interface. A caller branches on the code; the message is
#: prose that may be improved without breaking anyone.
ERROR_UNKNOWN_TOOL = "unknown_tool"
ERROR_INVALID_INPUT = "invalid_input"
ERROR_UNKNOWN_FUNCTION = "unknown_function"
ERROR_OUT_OF_BOUNDS = "out_of_bounds"
ERROR_NOT_FOUND = "not_found"
ERROR_ENGINE_UNAVAILABLE = "engine_unavailable"
ERROR_ANALYSIS_FAILED = "analysis_failed"
ERROR_SESSION_CLOSED = "session_closed"
ERROR_CONTRACT_VIOLATION = "contract_violation"
ERROR_INTERNAL = "internal_error"

ERROR_CODES = (
    ERROR_UNKNOWN_TOOL,
    ERROR_INVALID_INPUT,
    ERROR_UNKNOWN_FUNCTION,
    ERROR_OUT_OF_BOUNDS,
    ERROR_NOT_FOUND,
    ERROR_ENGINE_UNAVAILABLE,
    ERROR_ANALYSIS_FAILED,
    ERROR_SESSION_CLOSED,
    ERROR_CONTRACT_VIOLATION,
    ERROR_INTERNAL,
)


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str
    field: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "field": self.field}


@dataclass(frozen=True)
class ToolResult:
    """The complete answer to one tool call, success or failure."""

    tool: str
    ok: bool
    data: dict[str, Any] | None = None
    error: ToolError | None = None

    @classmethod
    def success(cls, tool: str, data: dict[str, Any]) -> ToolResult:
        return cls(tool=tool, ok=True, data=data)

    @classmethod
    def failure(cls, tool: str, code: str, message: str, field: str | None = None) -> ToolResult:
        return cls(tool=tool, ok=False, error=ToolError(code, message, field))

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "data": self.data,
            "error": None if self.error is None else self.error.as_dict(),
        }


@dataclass(frozen=True)
class ToolSpec:
    """A tool's whole contract: what it does, what it takes, what it returns.

    `max_output_items` is stated rather than implied. A caller planning a budget
    needs to know the ceiling before it calls, and the dispatcher enforces it
    afterwards so a tool cannot quietly exceed its own declaration.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: Callable[[Any, dict[str, Any]], dict[str, Any]]
    max_output_items: int = 0
    result_field: str | None = None
    failure_modes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        validate_schema(self.input_schema)
        validate_schema(self.output_schema)
        if self.result_field is not None and self.result_field not in self.output_schema.get(
            "properties", {}
        ):
            raise ValueError(
                f"{self.name}: result_field {self.result_field!r} is not in the output"
            )
        for code in self.failure_modes:
            if code not in ERROR_CODES:
                raise ValueError(f"{self.name}: unknown failure mode {code!r}")

    def describe(self) -> dict[str, Any]:
        """The machine-readable card an agent would be handed."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "max_output_items": self.max_output_items,
            "result_field": self.result_field,
            "failure_modes": list(self.failure_modes),
        }
