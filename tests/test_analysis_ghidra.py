"""Ghidra integration tests.

Every test analyzes `firmware.stripped` only. Ground truth is read from the
symbols-on build *after* the analysis session is built, matching the evaluation
boundary in docs/synthetic-lab.md.

These are marked `ghidra` and skip with a reason when Ghidra or PyGhidra is
missing, so a contributor without Ghidra still gets a green, honest run.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import ground_truth_symbols, requires_ghidra, stripped_firmware

from ecu_recovery.analysis import ArchitectureConfig
from ecu_recovery.analysis.base import (
    InvalidRequestError,
    StaticAnalysisSession,
    UnknownFunctionError,
)
from ecu_recovery.analysis.ghidra import GhidraEngine
from ecu_recovery.analysis.models import function_id_for
from ecu_recovery.cli import main

pytestmark = [pytest.mark.ghidra, requires_ghidra]

CONTROLLER = "temperature_controller_v1"
PIPELINE = "multi_function_pipeline_v1"


@pytest.fixture(scope="module")
def controller(engine: GhidraEngine) -> Iterator[StaticAnalysisSession]:
    with engine.analyze_binary(stripped_firmware(CONTROLLER)) as session:
        yield session


@pytest.fixture(scope="module")
def pipeline(engine: GhidraEngine) -> Iterator[StaticAnalysisSession]:
    with engine.analyze_binary(stripped_firmware(PIPELINE)) as session:
        yield session


def test_engine_reports_itself_available_on_this_host(engine: GhidraEngine) -> None:
    assert engine.is_available() is True


def test_program_summary_records_what_was_detected(controller: StaticAnalysisSession) -> None:
    summary = controller.program

    assert summary.language_id == "x86:LE:64:default"
    assert summary.executable_format == "Mac OS X Mach-O"
    assert summary.image_base == 0x100000000
    assert summary.engine == "ghidra"
    assert summary.engine_version != "unknown"
    # Nothing was declared, so every requested field stays empty and a reader can
    # tell a detected value from an investigator-supplied one.
    assert summary.requested.language_id is None


def test_discovers_every_expected_function_in_the_stripped_controller(
    controller: StaticAnalysisSession,
) -> None:
    discovered = {function.start_address for function in controller.list_functions()}

    expected = set(ground_truth_symbols(CONTROLLER))

    assert expected <= discovered, f"missed {expected - discovered}"
    assert discovered == expected, f"unexpected extras {discovered - expected}"


def test_recovers_the_full_call_graph_of_the_pipeline_sample(
    pipeline: StaticAnalysisSession,
) -> None:
    functions = pipeline.list_functions()
    symbols = ground_truth_symbols(PIPELINE)
    by_name = {symbols[function.start_address]: function for function in functions}

    edges = {
        (symbols[function.start_address], symbols[int(callee, 16)])
        for function in functions
        for callee in function.callees
    }

    assert set(by_name) == set(symbols.values())
    assert edges == {
        ("main", "sample_probe"),
        ("sample_probe", "control_output"),
        ("control_output", "normalize_sensor"),
        ("control_output", "apply_gain"),
        ("control_output", "clamp_output"),
    }


def test_callers_and_callees_agree_with_the_function_record(
    pipeline: StaticAnalysisSession,
) -> None:
    symbols = ground_truth_symbols(PIPELINE)
    control_output = next(address for address, name in symbols.items() if name == "control_output")
    record = pipeline.get_function(control_output)

    callees = pipeline.get_callees(record.id)
    callers = pipeline.get_callers(record.id)

    assert {item.id for item in callees} == set(record.callees)
    assert {item.id for item in callers} == set(record.callers)
    assert {symbols[item.start_address] for item in callees} == {
        "normalize_sensor",
        "apply_gain",
        "clamp_output",
    }
    assert {symbols[item.start_address] for item in callers} == {"sample_probe"}


def test_decompiles_the_threshold_comparison(controller: StaticAnalysisSession) -> None:
    symbols = ground_truth_symbols(CONTROLLER)
    address = next(a for a, name in symbols.items() if name == "temperature_fan_on")

    result = controller.decompile_function(function_id_for(address))

    assert result.success is True
    assert result.function_id == function_id_for(address)
    # The source is `temperature > threshold`; the decompiler is free to render
    # that with the operands swapped, so assert on the comparison, not the text.
    assert "<" in result.text or ">" in result.text
    assert "return" in result.text


def test_disassembly_is_plain_records_with_real_bytes(
    controller: StaticAnalysisSession,
) -> None:
    symbols = ground_truth_symbols(CONTROLLER)
    address = next(a for a, name in symbols.items() if name == "temperature_fan_on")

    disassembly = controller.get_disassembly(function_id_for(address))

    assert disassembly.instructions
    assert disassembly.truncated is False
    first = disassembly.instructions[0]
    assert first.address == address
    assert first.mnemonic == "PUSH"
    assert first.operands == "RBP"
    assert first.bytes_hex == "55"
    assert isinstance(first.bytes_hex, str)


def test_disassembly_truncates_rather_than_returning_everything(
    pipeline: StaticAnalysisSession,
) -> None:
    symbols = ground_truth_symbols(PIPELINE)
    address = next(a for a, name in symbols.items() if name == "main")

    disassembly = pipeline.get_disassembly(function_id_for(address), limit=2)

    assert len(disassembly.instructions) == 2
    assert disassembly.truncated is True


def test_memory_regions_are_ordered_and_flagged(controller: StaticAnalysisSession) -> None:
    regions = controller.list_memory_regions()

    assert regions == tuple(sorted(regions, key=lambda region: region.start_address))
    text = next(region for region in regions if region.name == "__text")
    assert text.executable is True
    assert text.writable is False
    assert text.initialized is True


def test_read_bytes_returns_the_first_instruction_bytes(
    controller: StaticAnalysisSession,
) -> None:
    symbols = ground_truth_symbols(CONTROLLER)
    address = next(a for a, name in symbols.items() if name == "temperature_fan_on")

    window = controller.read_bytes(address, 4)

    assert window.start_address == address
    assert window.length == 4
    assert window.data_hex.startswith("55")
    assert len(window.data_hex) == 8


def test_read_bytes_rejects_an_unmapped_address(controller: StaticAnalysisSession) -> None:
    with pytest.raises(InvalidRequestError):
        controller.read_bytes(0xDEAD0000, 16)


def test_read_bytes_refuses_an_oversized_request(controller: StaticAnalysisSession) -> None:
    with pytest.raises(InvalidRequestError, match="exceeds"):
        controller.read_bytes(0x100000F40, 1_000_000)


def test_search_constant_finds_the_clamp_ceiling(pipeline: StaticAnalysisSession) -> None:
    """1000 is the documented clamp ceiling in the pipeline ground truth."""
    matches = pipeline.search_constant(1000)

    assert matches
    assert all(match.value == 1000 for match in matches)
    assert any(match.function_id is not None for match in matches)


def test_search_constant_returns_empty_for_an_absent_value(
    pipeline: StaticAnalysisSession,
) -> None:
    assert pipeline.search_constant(0x1234_5678_9AB) == ()


def test_cross_references_locate_the_call_site(pipeline: StaticAnalysisSession) -> None:
    symbols = ground_truth_symbols(PIPELINE)
    callee = next(a for a, name in symbols.items() if name == "control_output")
    caller = next(a for a, name in symbols.items() if name == "sample_probe")

    references = pipeline.get_cross_references(callee)

    calls = [reference for reference in references if reference.is_call]
    assert calls
    assert all(reference.to_address == callee for reference in calls)
    assert any(reference.from_function_id == function_id_for(caller) for reference in calls)


def test_lists_strings_from_the_binary(pipeline: StaticAnalysisSession) -> None:
    strings = pipeline.list_strings(limit=50)

    assert strings
    assert all(len(item.value) >= 4 for item in strings)
    assert strings == tuple(sorted(strings, key=lambda item: item.address))


def test_paging_returns_distinct_windows(pipeline: StaticAnalysisSession) -> None:
    first = pipeline.list_functions(limit=2, offset=0)
    second = pipeline.list_functions(limit=2, offset=2)

    assert len(first) == 2
    assert len(second) == 2
    assert {item.id for item in first}.isdisjoint({item.id for item in second})
    assert pipeline.function_count() == len(ground_truth_symbols(PIPELINE))


def test_unknown_function_address_raises_a_typed_error(
    controller: StaticAnalysisSession,
) -> None:
    with pytest.raises(UnknownFunctionError):
        controller.get_function(0x100000F41)


def test_export_is_json_serializable_and_leaks_no_java_objects(
    controller: StaticAnalysisSession,
) -> None:
    export = controller.export(include_decompilation=True)

    rendered = json.dumps(export.as_dict())
    payload = json.loads(rendered)

    assert payload["function_count"] == len(ground_truth_symbols(CONTROLLER))
    assert payload["program"]["engine"] == "ghidra"
    assert all(item["success"] for item in payload["decompilations"])
    # A leaked Java object would have failed json.dumps above; assert the shape
    # explicitly so the reason for this test survives a refactor.
    assert isinstance(payload["functions"][0]["start_address"], str)


def test_declared_architecture_is_recorded_alongside_the_detected_one(
    engine: GhidraEngine,
) -> None:
    architecture = ArchitectureConfig(
        language_id="x86:LE:64:default", processor_label="x86-64 laboratory target"
    )

    with engine.analyze_binary(
        stripped_firmware(CONTROLLER), architecture, analyze=False
    ) as session:
        summary = session.program

    assert summary.requested.language_id == "x86:LE:64:default"
    assert summary.requested.processor_label == "x86-64 laboratory target"
    assert summary.language_id == "x86:LE:64:default"


def test_analysis_writes_no_project_state_beside_the_firmware(
    engine: GhidraEngine,
) -> None:
    """Ghidra defaults to creating `<name>_ghidra/` next to the input file.

    The samples directory is a checked-in fixture set, so a stray project would
    dirty the working tree and could differ between runs. The engine passes an
    explicit temporary `project_location` to prevent it.
    """
    firmware = stripped_firmware(CONTROLLER)
    before = set(firmware.parent.iterdir())

    with engine.analyze_binary(firmware, analyze=False) as session:
        session.list_memory_regions()

    assert set(firmware.parent.iterdir()) == before


def test_temporary_project_directory_is_removed_on_close(engine: GhidraEngine) -> None:
    """Track only this session's directory; module-scoped sessions stay open."""
    temp_root = Path(tempfile.gettempdir())
    pattern = "ecu-recovery-ghidra-*"
    before = set(temp_root.glob(pattern))

    session = engine.analyze_binary(stripped_firmware(CONTROLLER), analyze=False)
    created = set(temp_root.glob(pattern)) - before
    assert len(created) == 1, f"expected one new project dir, got {created}"

    session.close()

    assert not created.pop().exists()


def test_session_rejects_use_after_close(engine: GhidraEngine) -> None:
    session = engine.analyze_binary(stripped_firmware(CONTROLLER), analyze=False)
    session.close()
    session.close()  # must tolerate a repeat call

    with pytest.raises(RuntimeError, match="closed"):
        session.list_functions()


def test_cli_analyze_writes_a_ghidra_export(tmp_path: Path) -> None:
    analysis_json = tmp_path / "analysis.json"

    exit_code = main(
        [
            "analyze",
            str(stripped_firmware(CONTROLLER)),
            "--processor",
            "x86-64",
            "--ghidra",
            "--database",
            str(tmp_path / "investigations.sqlite3"),
            "--report",
            str(tmp_path / "report.md"),
            "--analysis-json",
            str(analysis_json),
        ]
    )

    assert exit_code == 0
    payload = json.loads(analysis_json.read_text(encoding="utf-8"))
    assert payload["function_count"] == len(ground_truth_symbols(CONTROLLER))
    assert payload["program"]["language_id"] == "x86:LE:64:default"
    assert (tmp_path / "report.md").is_file()
