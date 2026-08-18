"""Bounded, schema-defined tools over the verified static-analysis layer.

`EVAL-STATIC-001` measured the deterministic layer before this surface exposed
it: function discovery and call-graph recovery are exact across the synthetic
corpus, with the recorded baseline in `artifacts/evals/`. That measurement is
the reason these tools are worth attaching to, and this node does not repeat it.

No model lives here. Tools derive facts; interpreting them is a later node's
job, and keeping the two apart is what makes an interpretation checkable
against the tool output that produced it.
"""

from __future__ import annotations

from .analysis_tools import (
    DEFAULT_INSTRUCTION_LIMIT,
    MAX_TEXT_CHARS,
    MAX_WARNINGS,
    SPECS,
    ToolContext,
    ToolFailure,
)
from .models import (
    ERROR_ANALYSIS_FAILED,
    ERROR_CODES,
    ERROR_CONTRACT_VIOLATION,
    ERROR_ENGINE_UNAVAILABLE,
    ERROR_INTERNAL,
    ERROR_INVALID_INPUT,
    ERROR_NOT_FOUND,
    ERROR_OUT_OF_BOUNDS,
    ERROR_SESSION_CLOSED,
    ERROR_UNKNOWN_FUNCTION,
    ERROR_UNKNOWN_TOOL,
    ToolError,
    ToolResult,
    ToolSpec,
)
from .registry import REGISTRY, ToolRegistry
from .schema import SchemaError, ValidationFailure, validate, validate_schema

__all__ = [
    "DEFAULT_INSTRUCTION_LIMIT",
    "ERROR_ANALYSIS_FAILED",
    "ERROR_CODES",
    "ERROR_CONTRACT_VIOLATION",
    "ERROR_ENGINE_UNAVAILABLE",
    "ERROR_INTERNAL",
    "ERROR_INVALID_INPUT",
    "ERROR_NOT_FOUND",
    "ERROR_OUT_OF_BOUNDS",
    "ERROR_SESSION_CLOSED",
    "ERROR_UNKNOWN_FUNCTION",
    "ERROR_UNKNOWN_TOOL",
    "MAX_TEXT_CHARS",
    "MAX_WARNINGS",
    "REGISTRY",
    "SPECS",
    "SchemaError",
    "ToolContext",
    "ToolError",
    "ToolFailure",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "ValidationFailure",
    "validate",
    "validate_schema",
]
