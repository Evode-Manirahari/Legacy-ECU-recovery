"""The ten bounded tools an agent is allowed to call.

Two boundaries define this layer.

The first is what a tool may touch. A tool receives an already-open analysis
session and nothing else: no paths, no engine, no configuration. There is
therefore no filesystem argument anywhere in this file, and no tool can open,
read, or write anything the caller did not already open for it. Deciding what
to analyze stays with whoever built the session, which is not the agent.

The second is what a tool may return. Every response is built from the plain
records in `analysis.models` through their own `as_dict`, so a Java object
cannot reach a caller, and every list carries an explicit bound plus a flag
saying whether it was cut short. A silently truncated list is worse than a short
one: it reads as a complete answer and gets reasoned about as if it were.

Bounds come from `analysis.base` rather than being reinvented here, so the tool
surface and the engine agree on what "too much" means.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..analysis.base import (
    DEFAULT_PAGE_SIZE,
    MAX_INSTRUCTIONS,
    MAX_READ_BYTES,
    MAX_RESULTS,
    StaticAnalysisSession,
    parse_address,
)
from .models import (
    ERROR_INVALID_INPUT,
    ERROR_NOT_FOUND,
    ERROR_OUT_OF_BOUNDS,
    ERROR_UNKNOWN_FUNCTION,
    ToolSpec,
)

#: Decompiler output is the one field with no natural item count, so it is
#: bounded by characters. The cut is reported, never silent.
MAX_TEXT_CHARS = 20_000
#: A disassembly listing inside `inspect_function` defaults small: an agent
#: usually wants the shape of a function before it wants every instruction.
DEFAULT_INSTRUCTION_LIMIT = 64
#: Warnings are diagnostic context, not the payload.
MAX_WARNINGS = 50


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool is allowed to reach.

    One field, deliberately. Widening this is how a bounded tool layer turns
    into general host access, so it should be an argued change rather than a
    convenient one.
    """

    session: StaticAnalysisSession


def _page(items: list[Any], limit: int, offset: int) -> dict[str, Any]:
    """Uniform paging envelope, so every list answer reads the same way."""
    window = items[:limit]
    has_more = len(items) > len(window)
    return {
        "items": window,
        "returned": len(window),
        "has_more": has_more,
        "next_offset": offset + len(window) if has_more else -1,
    }


def _truncate_text(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_TEXT_CHARS:
        return text, False
    return text[:MAX_TEXT_CHARS], True


def _resolve_function(context: ToolContext, function_id: str) -> Any:
    try:
        return context.session.get_function(function_id)
    except Exception as error:  # noqa: BLE001 - remapped to a structured code by the registry
        raise ToolFailure(ERROR_UNKNOWN_FUNCTION, str(error), "function_id") from error


class ToolFailure(Exception):
    """A tool refusing its input, carrying the code the caller should see."""

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


# --- schema fragments shared by several tools ---

_PAGING_OUTPUT = {
    "returned": {"type": "integer"},
    "has_more": {"type": "boolean"},
    "next_offset": {"type": "integer"},
}


def _limit(default: int = DEFAULT_PAGE_SIZE, maximum: int = MAX_RESULTS) -> dict[str, Any]:
    return {"type": "integer", "minimum": 1, "maximum": maximum, "default": default}


def _offset() -> dict[str, Any]:
    return {"type": "integer", "minimum": 0, "default": 0}


def _function_id() -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": 32}


# --- handlers ---


def binary_summary(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    session = context.session
    warnings = session.analysis_warnings()
    regions = session.list_memory_regions()
    return {
        "program": session.program.as_dict(),
        "function_count": session.function_count(),
        "memory_region_count": len(regions),
        "analysis_warnings": [item.as_dict() for item in warnings[:MAX_WARNINGS]],
        "analysis_warning_count": len(warnings),
    }


def list_functions(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    limit, offset = arguments["limit"], arguments["offset"]
    # Ask for one more than requested: that is how `has_more` can be honest
    # without a second round trip or a count that might disagree.
    probe = min(limit + 1, MAX_RESULTS)
    functions = list(context.session.list_functions(limit=probe, offset=offset))
    page = _page([item.as_dict() for item in functions], limit, offset)
    return {"functions": page.pop("items"), **page}


def inspect_function(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    record = _resolve_function(context, arguments["function_id"])
    limit = arguments["instruction_limit"]
    disassembly = context.session.get_disassembly(record.id, limit=limit)
    return {
        "function": record.as_dict(),
        "instructions": [item.as_dict() for item in disassembly.instructions],
        "instruction_count": len(disassembly.instructions),
        "instructions_truncated": bool(disassembly.truncated),
    }


def decompile_function(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    record = _resolve_function(context, arguments["function_id"])
    result = context.session.decompile_function(record.id, arguments["timeout_seconds"])
    text, truncated = _truncate_text(result.text)
    return {
        "function_id": result.function_id,
        "success": bool(result.success),
        "text": text,
        "text_truncated": truncated,
        "warnings": list(result.warnings),
    }


def get_callers(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    record = _resolve_function(context, arguments["function_id"])
    callers = [item.as_dict() for item in context.session.get_callers(record.id)]
    page = _page(callers, arguments["limit"], 0)
    return {"function_id": record.id, "callers": page.pop("items"), **page}


def get_callees(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    record = _resolve_function(context, arguments["function_id"])
    callees = [item.as_dict() for item in context.session.get_callees(record.id)]
    page = _page(callees, arguments["limit"], 0)
    return {"function_id": record.id, "callees": page.pop("items"), **page}


def get_cross_references(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    raw = arguments["address"]
    try:
        address = parse_address(raw)
    except Exception as error:  # noqa: BLE001 - a malformed address is caller input
        raise ToolFailure(ERROR_INVALID_INPUT, str(error), "address") from error
    limit = arguments["limit"]
    references = context.session.get_cross_references(address, limit=min(limit + 1, MAX_RESULTS))
    page = _page([item.as_dict() for item in references], limit, 0)
    return {"address": raw, "references": page.pop("items"), **page}


def list_strings(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    limit, offset = arguments["limit"], arguments["offset"]
    probe = min(limit + 1, MAX_RESULTS)
    strings = context.session.list_strings(
        limit=probe, offset=offset, minimum_length=arguments["minimum_length"]
    )
    page = _page([item.as_dict() for item in strings], limit, offset)
    return {"strings": page.pop("items"), **page}


def search_constant(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    limit = arguments["limit"]
    matches = context.session.search_constant(arguments["value"], limit=min(limit + 1, MAX_RESULTS))
    page = _page([item.as_dict() for item in matches], limit, 0)
    return {"value": arguments["value"], "matches": page.pop("items"), **page}


def inspect_memory_region(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    regions = context.session.list_memory_regions()
    name = arguments.get("name")
    selected = [item for item in regions if item.name == name] if name else list(regions)
    if name and not selected:
        raise ToolFailure(ERROR_NOT_FOUND, f"no memory region named {name!r}", "name")

    payload: dict[str, Any] = {
        "regions": [item.as_dict() for item in selected],
        "returned": len(selected),
        "has_more": False,
        "next_offset": -1,
        "bytes": [],
    }
    if not arguments["include_bytes"]:
        return payload
    if len(selected) != 1:
        raise ToolFailure(
            ERROR_INVALID_INPUT,
            "reading bytes needs exactly one region; pass name to choose it",
            "name",
        )
    region = selected[0]
    length = min(arguments["byte_limit"], MAX_READ_BYTES, region.size)
    try:
        window = context.session.read_bytes(region.start_address, length)
    except Exception as error:  # noqa: BLE001 - unreadable memory is a caller-visible outcome
        raise ToolFailure(ERROR_OUT_OF_BOUNDS, str(error), "byte_limit") from error
    payload["bytes"] = [window.as_dict()]
    payload["bytes_truncated"] = region.size > window.length
    return payload


# --- specifications ---

SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="binary_summary",
        description=(
            "Program metadata, counts, and the analyzer's own warnings for the open binary. "
            "Start here: it says what was loaded and what the engine could not establish."
        ),
        input_schema={"type": "object", "properties": {}},
        output_schema={
            "type": "object",
            "properties": {
                "program": {"type": "object"},
                "function_count": {"type": "integer"},
                "memory_region_count": {"type": "integer"},
                "analysis_warnings": {"type": "array", "items": {"type": "object"}},
                "analysis_warning_count": {"type": "integer"},
            },
            "required": ["program", "function_count", "memory_region_count"],
        },
        handler=binary_summary,
        max_output_items=MAX_WARNINGS,
        result_field="analysis_warnings",
        failure_modes=("session_closed",),
    ),
    ToolSpec(
        name="list_functions",
        description="Functions ordered by entry address, one page at a time.",
        input_schema={
            "type": "object",
            "properties": {"limit": _limit(), "offset": _offset()},
        },
        output_schema={
            "type": "object",
            "properties": {
                "functions": {"type": "array", "items": {"type": "object"}},
                **_PAGING_OUTPUT,
            },
            "required": ["functions", "returned", "has_more", "next_offset"],
        },
        handler=list_functions,
        max_output_items=MAX_RESULTS,
        result_field="functions",
        failure_modes=("invalid_input", "session_closed"),
    ),
    ToolSpec(
        name="inspect_function",
        description=(
            "One function's record plus a bounded disassembly listing. "
            "Identify functions by entry address; a stripped binary has no other stable name."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "function_id": _function_id(),
                "instruction_limit": _limit(DEFAULT_INSTRUCTION_LIMIT, MAX_INSTRUCTIONS),
            },
            "required": ["function_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "function": {"type": "object"},
                "instructions": {"type": "array", "items": {"type": "object"}},
                "instruction_count": {"type": "integer"},
                "instructions_truncated": {"type": "boolean"},
            },
            "required": ["function", "instructions", "instructions_truncated"],
        },
        handler=inspect_function,
        max_output_items=MAX_INSTRUCTIONS,
        result_field="instructions",
        failure_modes=("invalid_input", "unknown_function", "session_closed"),
    ),
    ToolSpec(
        name="decompile_function",
        description=(
            "Decompiler output for one function. A failed decompilation is reported "
            "as success=false with warnings, not as an error."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "function_id": _function_id(),
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300, "default": 30},
            },
            "required": ["function_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "function_id": {"type": "string"},
                "success": {"type": "boolean"},
                "text": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                "text_truncated": {"type": "boolean"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["function_id", "success", "text", "text_truncated"],
        },
        handler=decompile_function,
        max_output_items=MAX_TEXT_CHARS,
        result_field="text",
        failure_modes=("invalid_input", "unknown_function", "session_closed"),
    ),
    ToolSpec(
        name="get_callers",
        description="Functions that call the named function.",
        input_schema={
            "type": "object",
            "properties": {"function_id": _function_id(), "limit": _limit()},
            "required": ["function_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "function_id": {"type": "string"},
                "callers": {"type": "array", "items": {"type": "object"}},
                **_PAGING_OUTPUT,
            },
            "required": ["function_id", "callers", "returned", "has_more", "next_offset"],
        },
        handler=get_callers,
        max_output_items=MAX_RESULTS,
        result_field="callers",
        failure_modes=("invalid_input", "unknown_function", "session_closed"),
    ),
    ToolSpec(
        name="get_callees",
        description="Functions the named function calls.",
        input_schema={
            "type": "object",
            "properties": {"function_id": _function_id(), "limit": _limit()},
            "required": ["function_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "function_id": {"type": "string"},
                "callees": {"type": "array", "items": {"type": "object"}},
                **_PAGING_OUTPUT,
            },
            "required": ["function_id", "callees", "returned", "has_more", "next_offset"],
        },
        handler=get_callees,
        max_output_items=MAX_RESULTS,
        result_field="callees",
        failure_modes=("invalid_input", "unknown_function", "session_closed"),
    ),
    ToolSpec(
        name="get_cross_references",
        description="References that target an address, each citing where it came from.",
        input_schema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "minLength": 1, "maxLength": 32},
                "limit": _limit(),
            },
            "required": ["address"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "references": {"type": "array", "items": {"type": "object"}},
                **_PAGING_OUTPUT,
            },
            "required": ["address", "references", "returned", "has_more", "next_offset"],
        },
        handler=get_cross_references,
        max_output_items=MAX_RESULTS,
        result_field="references",
        failure_modes=("invalid_input", "session_closed"),
    ),
    ToolSpec(
        name="list_strings",
        description="Defined strings ordered by address, one page at a time.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": _limit(),
                "offset": _offset(),
                "minimum_length": {"type": "integer", "minimum": 1, "maximum": 256, "default": 4},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "strings": {"type": "array", "items": {"type": "object"}},
                **_PAGING_OUTPUT,
            },
            "required": ["strings", "returned", "has_more", "next_offset"],
        },
        handler=list_strings,
        max_output_items=MAX_RESULTS,
        result_field="strings",
        failure_modes=("invalid_input", "session_closed"),
    ),
    ToolSpec(
        name="search_constant",
        description=(
            "Where a program uses a value: instruction operands, and data objects code refers to. "
            "Bytes that merely equal the value are not a use of it and are not reported."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "value": {"type": "integer"},
                "limit": _limit(),
            },
            "required": ["value"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "value": {"type": "integer"},
                "matches": {"type": "array", "items": {"type": "object"}},
                **_PAGING_OUTPUT,
            },
            "required": ["value", "matches", "returned", "has_more", "next_offset"],
        },
        handler=search_constant,
        max_output_items=MAX_RESULTS,
        result_field="matches",
        failure_modes=("invalid_input", "session_closed"),
    ),
    ToolSpec(
        name="inspect_memory_region",
        description=(
            "The loaded memory map, or one named region, optionally with a bounded byte window. "
            "Reading bytes requires naming a single region."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "maxLength": 128, "default": ""},
                "include_bytes": {"type": "boolean", "default": False},
                "byte_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_READ_BYTES,
                    "default": 256,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "regions": {"type": "array", "items": {"type": "object"}},
                "bytes": {"type": "array", "items": {"type": "object"}},
                "bytes_truncated": {"type": "boolean"},
                **_PAGING_OUTPUT,
            },
            "required": ["regions", "returned", "has_more", "next_offset"],
        },
        handler=inspect_memory_region,
        # Bounds the region list. The byte window is bounded separately, by
        # `byte_limit`, which the schema caps at MAX_READ_BYTES.
        max_output_items=MAX_RESULTS,
        result_field="regions",
        failure_modes=("invalid_input", "not_found", "out_of_bounds", "session_closed"),
    ),
)
