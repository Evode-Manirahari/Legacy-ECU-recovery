"""Engine-free tests for the analysis vocabulary and its bounds.

These run on any host. They must never require Ghidra, because the point of the
adapter boundary is that the records and their limits are independently testable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ecu_recovery.analysis import to_storage_record
from ecu_recovery.analysis.base import (
    MAX_READ_BYTES,
    MAX_RESULTS,
    InvalidRequestError,
    parse_address,
    validate_page,
    validate_read_request,
)
from ecu_recovery.analysis.ghidra import (
    GhidraEngine,
    find_ghidra_install_dir,
    read_ghidra_version,
)
from ecu_recovery.analysis.models import (
    AnalysisExport,
    ArchitectureConfig,
    DecompilerResult,
    FunctionRecord,
    MemoryRegion,
    ProgramSummary,
    StringRecord,
    function_id_for,
    render_address,
)


def _function(address: int = 0x100000F40, name: str = "FUN_100000f40") -> FunctionRecord:
    return FunctionRecord(
        id=function_id_for(address),
        name=name,
        start_address=address,
        end_address=address + 12,
        size=13,
        callees=("0x100000f50",),
    )


def test_function_id_is_derived_from_the_entry_address() -> None:
    assert function_id_for(0x923A) == "0x0000923a"
    assert render_address(0) == "0x00000000"


def test_memory_region_size_is_inclusive_of_both_endpoints() -> None:
    region = MemoryRegion("__text", 0x1000, 0x1003, True, False, True, True)

    assert region.size == 4


def test_export_serializes_to_stable_json() -> None:
    export = AnalysisExport(
        program=ProgramSummary(
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
        ),
        memory_regions=(MemoryRegion("__text", 0x100000F40, 0x100000FB7, True, False, True, True),),
        functions=(_function(),),
        strings=(StringRecord(0x10000101F, "main", 5, "string"),),
        decompilations=(DecompilerResult("0x100000f40", "bool f(void){return 1;}", True),),
    )

    rendered = json.loads(json.dumps(export.as_dict()))

    assert rendered["schema_version"] == 1
    assert rendered["function_count"] == 1
    assert rendered["functions"][0]["start_address"] == "0x100000f40"
    assert rendered["program"]["language_id"] == "x86:LE:64:default"
    assert rendered["memory_regions"][0]["size"] == 120
    assert rendered["decompilations"][0]["success"] is True


def test_failed_decompilation_is_a_result_not_an_exception() -> None:
    result = DecompilerResult("0x1000", "", False, ("timed out",))

    assert result.as_dict()["success"] is False
    assert result.as_dict()["warnings"] == ["timed out"]


def test_analysis_record_narrows_to_the_storage_record() -> None:
    stored = to_storage_record(_function(), decompilation="int f(void){return 0;}")

    assert stored.address == 0x100000F40
    assert stored.name == "FUN_100000f40"
    assert stored.size == 13
    assert stored.decompilation == "int f(void){return 0;}"


@pytest.mark.parametrize(
    "value,expected",
    [(0x923A, 0x923A), ("0x923A", 0x923A), ("0x0000923a", 0x923A), ("37946", 37946)],
)
def test_parse_address_accepts_ints_hex_and_function_ids(value: int | str, expected: int) -> None:
    assert parse_address(value) == expected


@pytest.mark.parametrize("value", ["", "zzz", "0xnope", -1])
def test_parse_address_rejects_malformed_input(value: int | str) -> None:
    with pytest.raises(InvalidRequestError):
        parse_address(value)


@pytest.mark.parametrize(
    "start,length",
    [(-1, 16), (0, 0), (0, -4), (0, MAX_READ_BYTES + 1)],
)
def test_read_requests_are_bounded(start: int, length: int) -> None:
    with pytest.raises(InvalidRequestError):
        validate_read_request(start, length)


def test_read_request_at_the_limit_is_allowed() -> None:
    validate_read_request(0x8000, MAX_READ_BYTES)


@pytest.mark.parametrize("limit,offset", [(0, 0), (-1, 0), (MAX_RESULTS + 1, 0), (10, -1)])
def test_paging_is_bounded(limit: int, offset: int) -> None:
    with pytest.raises(InvalidRequestError):
        validate_page(limit, offset)


def test_engine_reports_unavailable_instead_of_raising_on_a_bare_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GHIDRA_INSTALL_DIR", raising=False)
    monkeypatch.delenv("GHIDRA_HOME", raising=False)

    engine = GhidraEngine(install_dir=None)
    engine._install_dir = None  # simulate a host with no installation

    assert engine.is_available() is False


def test_engine_rejects_a_missing_firmware_path_before_starting_a_jvm(tmp_path: Path) -> None:
    engine = GhidraEngine()

    with pytest.raises(InvalidRequestError, match="is not a file"):
        engine.analyze_binary(tmp_path / "absent.bin")


def test_install_discovery_prefers_the_configured_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "ghidra"
    (install / "Ghidra").mkdir(parents=True)
    (install / "Ghidra" / "application.properties").write_text(
        "application.version=12.1.2\n", encoding="utf-8"
    )
    monkeypatch.setenv("GHIDRA_INSTALL_DIR", str(install))

    assert find_ghidra_install_dir() == install.resolve()
    assert read_ghidra_version(install) == "12.1.2"


def test_version_is_reported_as_unknown_when_properties_are_unreadable(tmp_path: Path) -> None:
    assert read_ghidra_version(tmp_path) == "unknown"
