"""Dispatch: the single door every tool call goes through.

Putting validation, error mapping, and bound enforcement here rather than in
each tool means a new tool cannot forget any of them. A handler that raises a
Java-side error, returns something off its own schema, or overruns its declared
size is caught at this boundary and turned into a structured refusal.

Nothing here executes caller-supplied code, and no tool name is resolved by
attribute lookup, so an unknown name is a plain lookup miss rather than a way
to reach something that was never meant to be a tool.
"""

from __future__ import annotations

from typing import Any

from ..analysis.base import (
    AnalysisError,
    EngineUnavailableError,
    InvalidRequestError,
    UnknownFunctionError,
)
from .analysis_tools import SPECS, ToolContext, ToolFailure
from .models import (
    ERROR_ANALYSIS_FAILED,
    ERROR_CONTRACT_VIOLATION,
    ERROR_ENGINE_UNAVAILABLE,
    ERROR_INTERNAL,
    ERROR_INVALID_INPUT,
    ERROR_SESSION_CLOSED,
    ERROR_UNKNOWN_FUNCTION,
    ERROR_UNKNOWN_TOOL,
    ToolResult,
    ToolSpec,
)
from .schema import validate


class ToolRegistry:
    """The catalog of callable tools, and the only way to call one."""

    def __init__(self, specs: tuple[ToolSpec, ...] = SPECS) -> None:
        duplicates = {spec.name for spec in specs if [s.name for s in specs].count(spec.name) > 1}
        if duplicates:
            raise ValueError(f"duplicate tool names: {sorted(duplicates)}")
        self._specs = {spec.name: spec for spec in specs}

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def catalog(self) -> list[dict[str, Any]]:
        """Every tool's contract, ordered, ready to hand to a caller."""
        return [self._specs[name].describe() for name in self.names()]

    def call(self, name: str, context: ToolContext, arguments: Any = None) -> ToolResult:
        """Run one tool. Never raises; every outcome is a `ToolResult`."""
        spec = self._specs.get(name)
        if spec is None:
            return ToolResult.failure(
                name,
                ERROR_UNKNOWN_TOOL,
                f"no tool named {name!r}; available tools are {list(self.names())}",
            )

        parsed, failure = validate({} if arguments is None else arguments, spec.input_schema)
        if failure is not None or parsed is None:
            message = "arguments were not an object" if failure is None else failure.message
            field = None if failure is None else failure.field
            return ToolResult.failure(name, ERROR_INVALID_INPUT, message, field)

        try:
            data = spec.handler(context, parsed)
        except ToolFailure as error:
            return ToolResult.failure(name, error.code, error.message, error.field)
        except UnknownFunctionError as error:
            return ToolResult.failure(name, ERROR_UNKNOWN_FUNCTION, str(error), "function_id")
        except InvalidRequestError as error:
            return ToolResult.failure(name, ERROR_INVALID_INPUT, str(error))
        except EngineUnavailableError as error:
            return ToolResult.failure(name, ERROR_ENGINE_UNAVAILABLE, str(error))
        except AnalysisError as error:
            # `session is closed` is the one AnalysisError a caller can act on
            # differently, so it gets its own code rather than a generic one.
            code = ERROR_SESSION_CLOSED if "closed" in str(error) else ERROR_ANALYSIS_FAILED
            return ToolResult.failure(name, code, str(error))
        except Exception as error:  # noqa: BLE001 - a tool must not leak a traceback to a caller
            return ToolResult.failure(name, ERROR_INTERNAL, f"{type(error).__name__}: {error}")

        violation = self._contract_violation(spec, data)
        if violation is not None:
            return ToolResult.failure(name, ERROR_CONTRACT_VIOLATION, violation)
        return ToolResult.success(name, data)

    @staticmethod
    def _contract_violation(spec: ToolSpec, data: Any) -> str | None:
        """Hold a tool to its own declaration before the caller ever sees it."""
        checked, failure = validate(data, spec.output_schema)
        if failure is not None or checked is None:
            detail = "output was not an object" if failure is None else failure.message
            return f"{spec.name} returned output off its own schema: {detail}"
        if spec.result_field is None or spec.max_output_items <= 0:
            return None
        payload = data.get(spec.result_field)
        size = len(payload) if isinstance(payload, (list, str)) else 0
        if size > spec.max_output_items:
            return (
                f"{spec.name} returned {size} items in {spec.result_field!r}, "
                f"over its declared maximum of {spec.max_output_items}"
            )
        return None


#: The default registry. Constructed once so the catalog is stable.
REGISTRY = ToolRegistry()
