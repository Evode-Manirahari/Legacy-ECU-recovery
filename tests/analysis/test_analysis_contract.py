"""Engine-free checks on the analysis contract.

These run on any host, with or without Ghidra. The point of the adapter boundary
is that the vocabulary, the bounds, the serialization, and the warning model are
testable without a JVM; if any of that needed Ghidra, the boundary would not be
doing its job.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from analysis_support import (
    MINIMUM_SAMPLE_COUNT,
    PROJECT_ROOT,
    SAMPLE_IDS,
    ghidra_skip_reason,
)

from ecu_recovery.analysis import base as analysis_base
from ecu_recovery.analysis.base import (
    MAX_RESULTS,
    WARNING_DECOMPILATION_FAILED,
    WARNING_FUNCTIONS_TRUNCATED,
    StaticAnalysisEngine,
    StaticAnalysisSession,
)
from ecu_recovery.analysis.models import (
    CONSTANT_KIND_DATA,
    CONSTANT_KIND_OPERAND,
    AnalysisExport,
    AnalysisWarning,
    ArchitectureConfig,
    BinaryAnalysis,
    ByteWindow,
    CallEdge,
    ConstantMatch,
    CrossReference,
    DecompilerResult,
    DisassemblyResult,
    FunctionRecord,
    MemoryRegion,
    ProgramSummary,
    StringRecord,
    address_of_function_id,
    call_edges_from,
    function_id_for,
    sorted_warnings,
)
from ecu_recovery.analysis.render import render_analysis_summary

#: Verbatim from the GHIDRA-001 contract.
REQUIRED_SESSION_OPERATIONS = (
    "list_memory_regions",
    "list_functions",
    "get_function",
    "decompile_function",
    "get_callers",
    "get_callees",
    "get_cross_references",
    "list_strings",
    "search_constant",
    "read_bytes",
)


def _summary() -> ProgramSummary:
    return ProgramSummary(
        source_path="/tmp/firmware.stripped",
        program_name="firmware.stripped",
        language_id="x86:LE:64:default",
        compiler_spec_id="gcc",
        image_base=0x100000000,
        executable_format="Mac OS X Mach-O",
        executable_sha256="ab" * 32,
        engine="ghidra",
        engine_version="12.1.2",
        requested=ArchitectureConfig(processor_label="x86-64"),
        processor="x86",
        endian="little",
        address_size_bits=64,
        pointer_size_bytes=8,
        entry_points=(0x100000F30,),
    )


def _function(address: int, callees: tuple[str, ...] = ()) -> FunctionRecord:
    return FunctionRecord(
        id=function_id_for(address),
        name=f"FUN_{address:x}",
        start_address=address,
        end_address=address + 15,
        size=16,
        callees=callees,
    )


# --- the contract's required surface ---


def test_every_required_operation_exists_on_the_session() -> None:
    for operation in REQUIRED_SESSION_OPERATIONS:
        assert callable(getattr(StaticAnalysisSession, operation, None)), operation


def test_analyze_binary_is_the_engine_entry_point() -> None:
    assert callable(getattr(StaticAnalysisEngine, "analyze_binary", None))


def test_an_engine_must_compute_its_own_warnings() -> None:
    """A default of "no warnings" would be a claim no engine had checked."""
    assert "analysis_warnings" in StaticAnalysisSession.__abstractmethods__


def test_binary_analysis_is_the_named_result_model_and_keeps_its_old_name() -> None:
    assert AnalysisExport is BinaryAnalysis


def test_required_models_carry_the_contract_names() -> None:
    for model in (BinaryAnalysis, MemoryRegion, FunctionRecord, DecompilerResult, CrossReference):
        assert model.__name__ in {
            "BinaryAnalysis",
            "MemoryRegion",
            "FunctionRecord",
            "DecompilerResult",
            "CrossReference",
        }


def test_the_corpus_is_large_enough_for_the_parametrized_suites() -> None:
    assert len(SAMPLE_IDS) >= MINIMUM_SAMPLE_COUNT


# --- serialization ---


def test_export_carries_every_output_category_the_cli_must_report() -> None:
    analysis = BinaryAnalysis(
        program=_summary(),
        memory_regions=(MemoryRegion("__text", 0x100000F40, 0x100000FB7, True, False, True, True),),
        functions=(_function(0x100000F40, ("0x100000f50",)), _function(0x100000F50)),
        strings=(StringRecord(0x10000101F, "main", 5, "string"),),
        decompilations=(DecompilerResult("0x100000f40", "int f(void){return 0;}", True),),
        analysis_warnings=(AnalysisWarning("no-functions-discovered", "none", "error"),),
    )

    payload = json.loads(json.dumps(analysis.as_dict()))

    assert payload["program"]["processor"] == "x86"
    assert payload["memory_regions"][0]["name"] == "__text"
    assert payload["function_count"] == 2
    assert payload["functions"][0]["start_address"] == "0x100000f40"
    assert payload["call_relationships"] == [
        {
            "caller_id": "0x100000f40",
            "callee_id": "0x100000f50",
            "caller_address": "0x100000f40",
            "callee_address": "0x100000f50",
        }
    ]
    assert payload["analysis_warnings"] == [
        {
            "code": "no-functions-discovered",
            "severity": "error",
            "message": "none",
            "address": None,
        }
    ]


def test_program_summary_reports_detected_architecture_facts() -> None:
    payload = _summary().as_dict()

    assert payload["endian"] == "little"
    assert payload["address_size_bits"] == 64
    assert payload["pointer_size_bytes"] == 8
    assert payload["entry_points"] == ["0x100000f30"]
    assert payload["auto_analysis_ran"] is True


def test_a_constant_match_states_which_kind_of_evidence_it_is() -> None:
    operand = ConstantMatch(
        0x100000F61, 100, CONSTANT_KIND_OPERAND, operand_index=1, mnemonic="CMP"
    )
    data = ConstantMatch(
        0x100000F84,
        20,
        CONSTANT_KIND_DATA,
        data_type="undefined4",
        block_name="__const",
        reference_count=2,
    )

    assert operand.as_dict()["kind"] == "operand"
    assert data.as_dict()["kind"] == "data"
    assert data.as_dict()["reference_count"] == 2
    assert data.as_dict()["block_name"] == "__const"


def test_the_other_records_still_serialize() -> None:
    assert DisassemblyResult("0x1", (), True).as_dict()["truncated"] is True
    assert ByteWindow(0x1000, 2, "9090").as_dict()["data"] == "9090"
    assert CrossReference(0x10, 0x20, "CALL", True).as_dict()["is_call"] is True


# --- call relationships ---


def test_repeated_calls_to_one_callee_produce_one_edge() -> None:
    caller = _function(0x1000, ("0x00002000", "0x00002000", "0x00003000"))

    edges = call_edges_from((caller,))

    assert edges == (
        CallEdge("0x00001000", "0x00002000", 0x1000, 0x2000),
        CallEdge("0x00001000", "0x00003000", 0x1000, 0x3000),
    )


def test_call_edges_are_ordered_by_address_pair() -> None:
    functions = (_function(0x3000, ("0x00001000",)), _function(0x1000, ("0x00002000",)))

    edges = call_edges_from(functions)

    assert [edge.caller_address for edge in edges] == [0x1000, 0x3000]


def test_a_function_id_round_trips_through_its_address() -> None:
    assert address_of_function_id(function_id_for(0x100000F40)) == 0x100000F40


# --- warnings ---


def test_warnings_sort_by_severity_then_code_then_address() -> None:
    unordered = (
        AnalysisWarning("z-code", "third", "info"),
        AnalysisWarning("a-code", "second", "warning", address=0x20),
        AnalysisWarning("a-code", "first", "warning", address=0x10),
        AnalysisWarning("boom", "worst", "error"),
    )

    assert [item.message for item in sorted_warnings(unordered)] == [
        "worst",
        "first",
        "second",
        "third",
    ]


def test_identical_warnings_collapse_so_two_runs_agree() -> None:
    warning = AnalysisWarning("dup", "same", "info")

    assert sorted_warnings((warning, warning)) == (warning,)


def test_an_unknown_severity_sorts_last_rather_than_raising() -> None:
    ordered = sorted_warnings(
        (AnalysisWarning("a", "odd", "catastrophic"), AnalysisWarning("b", "known", "info"))
    )

    assert [item.message for item in ordered] == ["known", "odd"]


# --- export paging, on a fake engine ---


class _FakeSession(StaticAnalysisSession):
    """A session with no engine behind it, to exercise `export` alone."""

    def __init__(self, functions: tuple[FunctionRecord, ...], failing: frozenset[str]) -> None:
        self._functions = functions
        self._failing = failing
        self.pages: list[tuple[int, int]] = []

    @property
    def program(self) -> ProgramSummary:
        return _summary()

    def list_functions(self, limit: int = 100, offset: int = 0) -> tuple[FunctionRecord, ...]:
        self.pages.append((limit, offset))
        return self._functions[offset : offset + limit]

    def function_count(self) -> int:
        return len(self._functions)

    def get_function(self, address: int | str) -> FunctionRecord:
        raise NotImplementedError

    def get_disassembly(self, function_id: str, limit: int = 4096) -> DisassemblyResult:
        raise NotImplementedError

    def decompile_function(self, function_id: str, timeout_seconds: int = 30) -> DecompilerResult:
        if function_id in self._failing:
            return DecompilerResult(function_id, "", False, ("timed out",))
        return DecompilerResult(function_id, "int f(void){return 0;}", True)

    def get_callers(self, function_id: str) -> tuple[FunctionRecord, ...]:
        raise NotImplementedError

    def get_callees(self, function_id: str) -> tuple[FunctionRecord, ...]:
        raise NotImplementedError

    def get_cross_references(
        self, address: int | str, limit: int = MAX_RESULTS
    ) -> tuple[CrossReference, ...]:
        raise NotImplementedError

    def list_strings(
        self, limit: int = 100, offset: int = 0, minimum_length: int = 4
    ) -> tuple[StringRecord, ...]:
        return ()

    def list_memory_regions(self) -> tuple[MemoryRegion, ...]:
        return ()

    def read_bytes(self, start: int, length: int) -> ByteWindow:
        raise NotImplementedError

    def search_constant(self, value: int, limit: int = MAX_RESULTS) -> tuple[ConstantMatch, ...]:
        return ()

    def analysis_warnings(self) -> tuple[AnalysisWarning, ...]:
        return ()

    def close(self) -> None:
        return None


def test_export_pages_past_a_single_result_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """A firmware image with more functions than one page must export whole."""
    monkeypatch.setattr(analysis_base, "MAX_RESULTS", 4)
    functions = tuple(_function(0x1000 + index * 0x10) for index in range(10))
    session = _FakeSession(functions, frozenset())

    exported = session.export()

    assert exported.functions == functions
    assert session.pages == [(4, 0), (4, 4), (4, 8)]


def test_export_says_so_when_it_stops_early(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analysis_base, "MAX_RESULTS", 4)
    monkeypatch.setattr(analysis_base, "MAX_EXPORT_FUNCTIONS", 8)
    functions = tuple(_function(0x1000 + index * 0x10) for index in range(40))

    exported = _FakeSession(functions, frozenset()).export()

    assert len(exported.functions) == 8
    codes = [item.code for item in exported.analysis_warnings]
    assert WARNING_FUNCTIONS_TRUNCATED in codes


def test_a_failed_decompilation_becomes_a_warning_not_an_exception() -> None:
    functions = (_function(0x1000), _function(0x2000))
    session = _FakeSession(functions, frozenset({"0x00002000"}))

    exported = session.export(include_decompilation=True)

    failures = [
        item for item in exported.analysis_warnings if item.code == WARNING_DECOMPILATION_FAILED
    ]
    assert [item.address for item in failures] == [0x2000]
    assert failures[0].message == "timed out"
    assert [item.success for item in exported.decompilations] == [True, False]


# --- the boundary itself ---


def test_ghidra_tests_skip_with_a_stated_reason_on_a_host_without_ghidra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CI has no Ghidra. A silent skip there would hide a broken suite."""
    monkeypatch.setattr(
        "ecu_recovery.analysis.ghidra.GhidraEngine.install_dir",
        property(lambda self: None),
    )

    reason = ghidra_skip_reason()

    assert reason
    assert "ghidra" in reason.lower()


def test_importing_the_analysis_package_does_not_start_ghidra() -> None:
    """`doctor` imports this package on hosts with no Ghidra at all."""
    probe = (
        "import sys; import ecu_recovery.analysis; "
        "assert 'pyghidra' not in sys.modules; "
        "assert 'ecu_recovery.analysis.ghidra' not in sys.modules"
    )

    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=PROJECT_ROOT,
        env={"PYTHONPATH": str(Path(PROJECT_ROOT) / "src"), "PATH": ""},
    )

    assert result.returncode == 0, result.stderr


# --- rendering ---


def test_the_summary_renders_all_six_contract_categories() -> None:
    analysis = BinaryAnalysis(
        program=_summary(),
        memory_regions=(MemoryRegion("__text", 0x100000F40, 0x100000FB7, True, False, True, True),),
        functions=(_function(0x100000F40, ("0x100000f50",)), _function(0x100000F50)),
        strings=(),
        analysis_warnings=(
            AnalysisWarning("auto-analysis-skipped", "no auto-analysis", "warning", 0x100000F40),
        ),
    )

    rendered = render_analysis_summary(analysis)

    assert "binary metadata:" in rendered
    assert "memory map: 1 region(s)" in rendered
    assert "function count: 2" in rendered
    assert "function records:" in rendered
    assert "call relationships: 1 edge(s)" in rendered
    assert "0x100000f40 -> 0x100000f50" in rendered
    assert "analysis warnings: 1" in rendered
    assert "[warning] auto-analysis-skipped at 0x100000f40: no auto-analysis" in rendered


def test_a_truncated_listing_admits_that_it_is_truncated() -> None:
    analysis = BinaryAnalysis(
        program=_summary(),
        memory_regions=(),
        functions=tuple(_function(0x1000 + index * 0x10) for index in range(5)),
        strings=(),
    )

    rendered = render_analysis_summary(analysis, function_limit=2)

    assert "... 3 further function records in the serialized export" in rendered
