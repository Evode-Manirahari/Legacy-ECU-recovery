"""The tool layer against the real engine.

The fake-session tests prove the layer's own guarantees. These prove the layer
is actually wired to Ghidra: that what a tool reports matches what the analysis
session reports, that nothing Java-shaped escapes, and that two identical calls
answer identically.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from tools_support import PIPELINE, requires_ghidra, stripped_firmware

from ecu_recovery.analysis.base import StaticAnalysisSession
from ecu_recovery.analysis.ghidra import GhidraEngine
from ecu_recovery.tools import REGISTRY, ToolContext

pytestmark = [pytest.mark.ghidra, requires_ghidra]

_SESSION: StaticAnalysisSession | None = None


@pytest.fixture(scope="module")
def context() -> Iterator[ToolContext]:
    global _SESSION
    _SESSION = GhidraEngine().analyze_binary(stripped_firmware(PIPELINE))
    try:
        yield ToolContext(session=_SESSION)
    finally:
        _SESSION.close()
        _SESSION = None


def test_binary_summary_describes_what_was_loaded(context: ToolContext) -> None:
    result = REGISTRY.call("binary_summary", context)

    assert result.ok is True
    assert result.data is not None
    assert result.data["program"]["language_id"] == "x86:LE:64:default"
    assert result.data["function_count"] == 6
    assert result.data["memory_region_count"] > 0


def test_every_tool_result_survives_json(context: ToolContext) -> None:
    """A leaked Java object would fail here, which is the point of the boundary."""
    calls = [
        ("binary_summary", {}),
        ("list_functions", {"limit": 5}),
        ("list_strings", {"limit": 5}),
        ("search_constant", {"value": 1000}),
        ("inspect_memory_region", {}),
    ]
    for name, arguments in calls:
        result = REGISTRY.call(name, context, arguments)
        assert result.ok is True, (name, result.error)
        rendered = json.loads(json.dumps(result.as_dict()))
        assert rendered["tool"] == name


def test_a_tool_reports_what_the_session_reports(context: ToolContext) -> None:
    """The tool layer must not become a second, drifting source of truth."""
    listed = REGISTRY.call("list_functions", context, {"limit": 100})

    assert listed.data is not None
    from_tools = [item["start_address"] for item in listed.data["functions"]]
    from_session = [
        f"0x{item.start_address:08x}" for item in context.session.list_functions(limit=100)
    ]
    assert from_tools == from_session


def test_call_relationships_round_trip_through_the_tools(context: ToolContext) -> None:
    listed = REGISTRY.call("list_functions", context, {"limit": 100})
    assert listed.data is not None
    caller = next(item for item in listed.data["functions"] if item["callees"])

    callees = REGISTRY.call("get_callees", context, {"function_id": caller["id"]})

    assert callees.data is not None
    assert {item["id"] for item in callees.data["callees"]} == set(caller["callees"])
    for callee in callees.data["callees"]:
        back = REGISTRY.call("get_callers", context, {"function_id": callee["id"]})
        assert back.data is not None
        assert caller["id"] in {item["id"] for item in back.data["callers"]}


def test_inspect_function_returns_real_instruction_bytes(context: ToolContext) -> None:
    listed = REGISTRY.call("list_functions", context, {"limit": 1})
    assert listed.data is not None
    function_id = listed.data["functions"][0]["id"]

    result = REGISTRY.call("inspect_function", context, {"function_id": function_id})

    assert result.data is not None
    assert result.data["instructions"]
    first = result.data["instructions"][0]
    assert first["address"] == function_id
    assert first["bytes"]


def test_decompilation_is_returned_as_text_not_an_object(context: ToolContext) -> None:
    listed = REGISTRY.call("list_functions", context, {"limit": 1})
    assert listed.data is not None

    result = REGISTRY.call(
        "decompile_function", context, {"function_id": listed.data["functions"][0]["id"]}
    )

    assert result.data is not None
    assert result.data["success"] is True
    assert isinstance(result.data["text"], str)
    assert result.data["text_truncated"] is False


def test_search_constant_reports_evidence_kinds(context: ToolContext) -> None:
    """1000 is the documented clamp ceiling in this fixture."""
    result = REGISTRY.call("search_constant", context, {"value": 1000})

    assert result.data is not None
    assert result.data["returned"] > 0
    assert all(item["kind"] in ("operand", "data") for item in result.data["matches"])


def test_cross_references_cite_where_they_came_from(context: ToolContext) -> None:
    listed = REGISTRY.call("list_functions", context, {"limit": 100})
    assert listed.data is not None
    callee = next(item for item in listed.data["functions"] if item["callers"])

    result = REGISTRY.call("get_cross_references", context, {"address": callee["id"]})

    assert result.data is not None
    calls = [item for item in result.data["references"] if item["is_call"]]
    assert calls
    assert all(item["to_address"] == callee["id"] for item in calls)


def test_reading_bytes_requires_naming_one_region(context: ToolContext) -> None:
    refused = REGISTRY.call("inspect_memory_region", context, {"include_bytes": True})

    assert refused.error is not None
    assert refused.error.code == "invalid_input"

    allowed = REGISTRY.call(
        "inspect_memory_region",
        context,
        {"name": "__text", "include_bytes": True, "byte_limit": 16},
    )
    assert allowed.data is not None
    assert len(allowed.data["bytes"]) == 1
    assert len(allowed.data["bytes"][0]["data"]) == 32


def test_two_identical_calls_answer_identically(context: ToolContext) -> None:
    first = REGISTRY.call("list_functions", context, {"limit": 10})
    second = REGISTRY.call("list_functions", context, {"limit": 10})

    assert first.as_dict() == second.as_dict()


def test_the_tools_never_reach_the_hidden_ground_truth(context: ToolContext) -> None:
    """Nothing here may see the answer key, now or by later accident."""
    listed = REGISTRY.call("list_functions", context, {"limit": 100})
    assert listed.data is not None

    names = {item["name"] for item in listed.data["functions"]}
    # Ghidra names stripped functions FUN_<address> or `entry`; a real symbol
    # name would mean the symbols-on build had been read.
    assert all(name.startswith("FUN_") or name == "entry" for name in names), names

    summary = REGISTRY.call("binary_summary", context)
    assert summary.data is not None
    assert "firmware.symbols" not in json.dumps(summary.data)
