"""The tool contract, the dispatcher, and every failure path.

These run without Ghidra against a fake session, because paging, bounds,
truncation flags, and structured errors are properties of this layer rather
than of the engine. Keeping them engine-free means CI checks them on every push.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from tools_support import FakeSession, fake_context

from ecu_recovery.analysis.base import (
    MAX_INSTRUCTIONS,
    MAX_READ_BYTES,
    MAX_RESULTS,
    AnalysisError,
    EngineUnavailableError,
)
from ecu_recovery.tools import (
    ERROR_CODES,
    REGISTRY,
    SPECS,
    ToolContext,
    ToolRegistry,
    ToolSpec,
)

#: Verbatim from prompts/TOOLS-001.md.
REQUIRED_TOOLS = (
    "binary_summary",
    "list_functions",
    "inspect_function",
    "decompile_function",
    "get_callers",
    "get_callees",
    "get_cross_references",
    "list_strings",
    "search_constant",
    "inspect_memory_region",
)


# --- the contract every tool must satisfy ---


def test_every_required_tool_is_registered() -> None:
    assert set(REQUIRED_TOOLS) <= set(REGISTRY.names())


def test_no_tool_exists_that_the_contract_did_not_ask_for() -> None:
    """A tool surface grows by decision, not by accident."""
    assert set(REGISTRY.names()) == set(REQUIRED_TOOLS)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_each_tool_declares_a_complete_contract(spec: ToolSpec) -> None:
    assert spec.name
    assert len(spec.description) > 20, "a description an agent cannot act on is not a description"
    assert spec.input_schema["type"] == "object"
    assert spec.output_schema["type"] == "object"
    assert spec.output_schema.get("required"), "an output with nothing required promises nothing"
    assert spec.max_output_items > 0
    assert spec.failure_modes
    assert set(spec.failure_modes) <= set(ERROR_CODES)


def test_the_catalog_is_json_serializable() -> None:
    """It is handed to a caller as data, so it has to survive the wire."""
    catalog = json.loads(json.dumps(REGISTRY.catalog()))

    assert [item["name"] for item in catalog] == list(REGISTRY.names())
    assert all(item["input_schema"]["type"] == "object" for item in catalog)


def test_bounds_come_from_the_analysis_layer_rather_than_new_numbers() -> None:
    """The contract says build on the existing bounds; drift would be silent."""
    limits = {spec.name: spec.input_schema["properties"] for spec in SPECS}

    assert limits["list_functions"]["limit"]["maximum"] == MAX_RESULTS
    assert limits["inspect_function"]["instruction_limit"]["maximum"] == MAX_INSTRUCTIONS
    assert limits["inspect_memory_region"]["byte_limit"]["maximum"] == MAX_READ_BYTES


def test_no_tool_accepts_a_filesystem_path() -> None:
    """The layer cannot open anything: it is handed a session and nothing else."""
    for spec in SPECS:
        for name in spec.input_schema.get("properties", {}):
            assert not any(token in name for token in ("path", "file", "dir", "url")), (
                f"{spec.name} takes {name!r}, which would widen this beyond a bounded tool"
            )
    assert ToolContext.__dataclass_fields__.keys() == {"session"}


def test_a_duplicate_tool_name_is_refused() -> None:
    with pytest.raises(ValueError, match="duplicate tool names"):
        ToolRegistry((SPECS[0], SPECS[0]))


# --- valid input ---


def test_a_valid_call_returns_data_and_no_error() -> None:
    result = REGISTRY.call("binary_summary", fake_context())

    assert result.ok is True
    assert result.error is None
    assert result.data is not None
    assert result.data["function_count"] == 5


@pytest.mark.parametrize("name", REQUIRED_TOOLS)
def test_every_tool_answers_a_well_formed_call(name: str) -> None:
    arguments: dict[str, Any] = {}
    if name in ("inspect_function", "decompile_function", "get_callers", "get_callees"):
        arguments = {"function_id": "0x00001000"}
    if name == "get_cross_references":
        arguments = {"address": "0x1000"}
    if name == "search_constant":
        arguments = {"value": 42}

    result = REGISTRY.call(name, fake_context(), arguments)

    assert result.ok is True, result.error
    assert json.dumps(result.as_dict())


# --- invalid input ---


def test_an_unknown_tool_says_what_is_available() -> None:
    result = REGISTRY.call("rm_rf", fake_context())

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "unknown_tool"
    assert "list_functions" in result.error.message


@pytest.mark.parametrize(
    "name,arguments,field",
    [
        ("list_functions", {"limit": 0}, "limit"),
        ("list_functions", {"offset": -1}, "offset"),
        ("list_functions", {"limit": "ten"}, "limit"),
        ("list_functions", {"unexpected": 1}, "unexpected"),
        ("inspect_function", {}, "function_id"),
        ("search_constant", {}, "value"),
        ("get_cross_references", {"address": ""}, "address"),
    ],
)
def test_invalid_input_is_refused_with_the_offending_field(
    name: str, arguments: dict[str, Any], field: str
) -> None:
    result = REGISTRY.call(name, fake_context(), arguments)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "invalid_input"
    assert result.error.field == field


def test_a_malformed_address_is_caller_error_not_a_crash() -> None:
    result = REGISTRY.call("get_cross_references", fake_context(), {"address": "not-an-address"})

    assert result.error is not None
    assert result.error.code == "invalid_input"
    assert result.error.field == "address"


def test_arguments_that_are_not_an_object_are_refused() -> None:
    result = REGISTRY.call("list_functions", fake_context(), [1, 2, 3])

    assert result.error is not None
    assert result.error.code == "invalid_input"


# --- oversized requests ---


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("list_functions", {"limit": MAX_RESULTS + 1}),
        (
            "inspect_function",
            {"function_id": "0x00001000", "instruction_limit": MAX_INSTRUCTIONS + 1},
        ),
        ("inspect_memory_region", {"byte_limit": MAX_READ_BYTES + 1}),
        ("list_strings", {"limit": MAX_RESULTS + 1}),
        ("search_constant", {"value": 1, "limit": MAX_RESULTS + 1}),
        ("decompile_function", {"function_id": "0x00001000", "timeout_seconds": 100_000}),
    ],
)
def test_an_oversized_request_is_refused_before_it_runs(
    name: str, arguments: dict[str, Any]
) -> None:
    result = REGISTRY.call(name, fake_context(), arguments)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "invalid_input"


def test_decompiler_text_is_bounded_and_says_so() -> None:
    from ecu_recovery.tools import MAX_TEXT_CHARS

    context = ToolContext(session=FakeSession(decompiled_text="x" * (MAX_TEXT_CHARS + 500)))

    result = REGISTRY.call("decompile_function", context, {"function_id": "0x00001000"})

    assert result.data is not None
    assert len(result.data["text"]) == MAX_TEXT_CHARS
    assert result.data["text_truncated"] is True


# --- pagination ---


def test_pagination_reports_more_and_where_to_resume() -> None:
    context = ToolContext(session=FakeSession(function_count=10))

    first = REGISTRY.call("list_functions", context, {"limit": 4})

    assert first.data is not None
    assert first.data["returned"] == 4
    assert first.data["has_more"] is True
    assert first.data["next_offset"] == 4


def test_following_next_offset_walks_the_whole_list_without_repeats() -> None:
    context = ToolContext(session=FakeSession(function_count=10))
    seen: list[str] = []
    offset = 0
    for _ in range(10):
        result = REGISTRY.call("list_functions", context, {"limit": 3, "offset": offset})
        assert result.data is not None
        seen.extend(item["id"] for item in result.data["functions"])
        if not result.data["has_more"]:
            break
        offset = result.data["next_offset"]

    assert len(seen) == 10
    assert len(set(seen)) == 10


def test_the_last_page_says_there_is_no_next() -> None:
    context = ToolContext(session=FakeSession(function_count=3))

    result = REGISTRY.call("list_functions", context, {"limit": 10})

    assert result.data is not None
    assert result.data["has_more"] is False
    assert result.data["next_offset"] == -1


def test_a_truncated_disassembly_is_flagged() -> None:
    result = REGISTRY.call(
        "inspect_function", fake_context(), {"function_id": "0x00001000", "instruction_limit": 2}
    )

    assert result.data is not None
    assert result.data["instructions_truncated"] is True


# --- tool failure ---


def test_a_closed_session_is_reported_as_such() -> None:
    result = REGISTRY.call("binary_summary", ToolContext(session=FakeSession(closed=True)))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "session_closed"


def test_an_engine_failure_is_reported_not_raised() -> None:
    context = ToolContext(session=FakeSession(raises=AnalysisError("ghidra fell over")))

    result = REGISTRY.call("binary_summary", context)

    assert result.error is not None
    assert result.error.code == "analysis_failed"


def test_a_missing_engine_has_its_own_code() -> None:
    context = ToolContext(session=FakeSession(raises=EngineUnavailableError("no ghidra")))

    result = REGISTRY.call("binary_summary", context)

    assert result.error is not None
    assert result.error.code == "engine_unavailable"


def test_an_unknown_function_is_reported_against_its_field() -> None:
    result = REGISTRY.call("inspect_function", fake_context(), {"function_id": "0xdeadbeef"})

    assert result.error is not None
    assert result.error.code == "unknown_function"
    assert result.error.field == "function_id"


def test_an_unexpected_exception_never_escapes_as_a_traceback() -> None:
    context = ToolContext(session=FakeSession(raises=ZeroDivisionError("boom")))

    result = REGISTRY.call("binary_summary", context)

    assert result.error is not None
    assert result.error.code == "internal_error"
    assert "ZeroDivisionError" in result.error.message


def test_a_tool_that_breaks_its_own_output_schema_is_caught() -> None:
    def broken(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"unexpected": True}

    spec = ToolSpec(
        name="broken",
        description="returns something other than what it declared, on purpose",
        input_schema={"type": "object", "properties": {}},
        output_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
        handler=broken,
        max_output_items=1,
        failure_modes=("internal_error",),
    )

    result = ToolRegistry((spec,)).call("broken", fake_context())

    assert result.error is not None
    assert result.error.code == "contract_violation"


def test_a_tool_that_exceeds_its_declared_size_is_caught() -> None:
    def oversized(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"items": list(range(50))}

    spec = ToolSpec(
        name="oversized",
        description="returns more items than it said it ever would, on purpose",
        input_schema={"type": "object", "properties": {}},
        output_schema={
            "type": "object",
            "properties": {"items": {"type": "array", "items": {"type": "integer"}}},
            "required": ["items"],
        },
        handler=oversized,
        max_output_items=10,
        result_field="items",
        failure_modes=("internal_error",),
    )

    result = ToolRegistry((spec,)).call("oversized", fake_context())

    assert result.error is not None
    assert result.error.code == "contract_violation"
    assert "over its declared maximum" in result.error.message


def test_a_failed_result_carries_no_data() -> None:
    result = REGISTRY.call("nope", fake_context())

    assert result.data is None
    assert result.as_dict()["data"] is None


# --- the design document must describe what actually ships ---


def test_tool_design_documents_every_registered_tool() -> None:
    """A design doc that drifts from the code is worse than none."""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2].joinpath("TOOL_DESIGN.md").read_text(encoding="utf-8")
    )

    for name in REGISTRY.names():
        assert f"`{name}`" in text, f"{name} is not documented in TOOL_DESIGN.md"
    for code in ERROR_CODES:
        assert f"`{code}`" in text, f"error code {code} is not documented in TOOL_DESIGN.md"


def test_tool_design_states_each_declared_maximum() -> None:
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2].joinpath("TOOL_DESIGN.md").read_text(encoding="utf-8")
    )

    for spec in SPECS:
        assert str(spec.max_output_items) in text, (
            f"{spec.name} declares max {spec.max_output_items}, which the doc never states"
        )
