"""What counts as evidence, and what the engine refuses to claim.

The rule carried from DATA-001: a constant is recovered when analysis has a
semantically relevant reason to believe the program uses it - an instruction
operand, or a data object that code refers to. A byte sequence that merely
equals the value is not evidence. A Mach-O header is dense with small integers,
so an engine that scanned bytes would report a pile of recoveries no
instruction supports, and evaluation downstream would score the fixture instead
of the tool.

The other half of this file is deterministic failure: every bad request has to
come back as a typed error rather than a Java stack trace.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from analysis_support import (
    analysis_engine,
    close_samples_after_the_run,  # noqa: F401 - session teardown, used by pytest
    ground_truth,
    ground_truth_symbols,
    open_sample,
    requires_ghidra,
    stripped_firmware,
)

from ecu_recovery.analysis.base import (
    MAX_RESULTS,
    WARNING_ENGINE_DIAGNOSTIC,
    WARNING_IMAGE_BASE_OVERRIDDEN,
    WARNING_LANGUAGE_DECLARED,
    AnalysisError,
    InvalidRequestError,
    UnknownFunctionError,
)
from ecu_recovery.analysis.ghidra import GhidraSession
from ecu_recovery.analysis.models import (
    CONSTANT_KIND_DATA,
    CONSTANT_KIND_OPERAND,
    ArchitectureConfig,
)

pytestmark = [pytest.mark.ghidra, requires_ghidra]

LOOKUP_1D = "lookup_1d_v1"
LOOKUP_2D = "lookup_2d_v1"
CONTROLLER = "temperature_controller_v1"

#: `lookup_2d_v1`'s calibration table, flattened. The compiler puts it in
#: `__const`; the ground-truth file is the authority on the values.
LOOKUP_2D_TABLE = (10, 12, 15, 18, 14, 18, 22, 26, 19, 24, 30, 36)


# --- what qualifies as evidence ---


def test_an_operand_match_points_at_the_instruction_that_uses_the_value() -> None:
    session = open_sample(LOOKUP_1D)

    matches = [
        match
        for match in session.search_constant(75)
        if match.kind == CONSTANT_KIND_OPERAND and match.function_id is not None
    ]

    assert matches
    for match in matches:
        assert match.operand_index is not None
        assert match.mnemonic
        instructions = session.get_disassembly(str(match.function_id)).instructions
        located = [item for item in instructions if item.address == match.address]
        assert located, f"no instruction at {match.address:#x}"
        assert located[0].mnemonic == match.mnemonic


def test_a_calibration_table_entry_is_recovered_as_referenced_data() -> None:
    """The capability an operand-only search cannot have.

    `lookup_1d_v1` reaches its axis table through a base register, so none of
    the table values ever appear as an immediate.
    """
    session = open_sample(LOOKUP_1D)

    matches = session.search_constant(20)

    assert matches
    assert all(match.kind == CONSTANT_KIND_DATA for match in matches)
    assert all(match.block_name == "__const" for match in matches)
    assert all(match.reference_count >= 1 for match in matches)
    # The reading function is named, so a downstream claim can cite it.
    assert all(match.function_id is not None for match in matches)


def test_every_data_match_really_is_referenced_by_code() -> None:
    session = open_sample(LOOKUP_1D)
    regions = session.list_memory_regions()

    for value in ground_truth(LOOKUP_1D)["expected_constants"]:
        for match in session.search_constant(value):
            if match.kind != CONSTANT_KIND_DATA:
                continue
            assert any(
                region.name == match.block_name and region.contains(match.address)
                for region in regions
            ), f"{match.address:#x} claims block {match.block_name}"
            references = session.get_cross_references(match.address)
            assert references, f"{match.address:#x} was reported with no reference at all"
            assert match.reference_count <= len(references)


def test_matching_bytes_that_no_instruction_touches_are_never_reported() -> None:
    """The regression this rule exists for.

    The Mach-O header of every fixture holds zero-valued words. None of them is
    a use of the constant zero, and reporting them would manufacture a recovery
    for a value the compiler materialises with `xor`.
    """
    session = open_sample(CONTROLLER)
    header = next(region for region in session.list_memory_regions() if region.name == "__TEXT")

    window = session.read_bytes(header.start_address, 64)
    assert "00000000" in window.data_hex, "the header no longer contains a zero word"

    assert not [match for match in session.search_constant(0) if header.contains(match.address)]


def test_an_unreferenced_table_stays_reachable_through_the_documented_route() -> None:
    """What GHIDRA-001 offers when `search_constant` cannot claim a value.

    `lookup_2d_v1` indexes its table by a computed offset, so Ghidra resolves a
    reference to the table base and to no individual entry. The entries are
    therefore not reported as constants - but the base reference plus the region
    map plus `read_bytes` still reach them, deterministically, without guessing.
    """
    session = open_sample(LOOKUP_2D)
    const = next(region for region in session.list_memory_regions() if region.name == "__const")

    references = session.get_cross_references(const.start_address)
    assert [item for item in references if item.from_function_id is not None], (
        "no function refers to the calibration table base"
    )

    window = session.read_bytes(const.start_address, const.size)
    decoded = struct.unpack(f"<{const.size // 4}i", bytes.fromhex(window.data_hex))

    assert decoded == LOOKUP_2D_TABLE


def test_repeated_constant_searches_agree() -> None:
    session = open_sample(LOOKUP_1D)

    assert session.search_constant(20) == session.search_constant(20)


def test_a_constant_search_honours_its_limit() -> None:
    session = open_sample(LOOKUP_1D)

    assert len(session.search_constant(75, limit=1)) == 1
    assert session.search_constant(75, limit=1) == session.search_constant(75)[:1]


def test_a_value_the_program_never_uses_returns_nothing() -> None:
    assert open_sample(LOOKUP_1D).search_constant(0x1234_5678_9AB) == ()


# --- warnings ---


def test_a_declared_load_configuration_is_reported_back() -> None:
    """An investigator's guess must never read as a detected fact."""
    architecture = ArchitectureConfig(
        language_id="x86:LE:64:default", base_address=0x100000000, processor_label="x86-64"
    )

    with analysis_engine().analyze_binary(
        stripped_firmware(CONTROLLER), architecture, analyze=False
    ) as session:
        codes = {item.code for item in session.analysis_warnings()}

    assert WARNING_LANGUAGE_DECLARED in codes
    assert WARNING_IMAGE_BASE_OVERRIDDEN in codes


def test_ghidra_s_own_complaints_are_surfaced_as_warnings() -> None:
    """The corpus is clean, so the engine files no complaints on it.

    A damaged image is where this path matters, and there is no fixture for one.
    The bookmark is therefore planted directly: it is the only way to prove the
    mapping from Ghidra's diagnostics to ours works before a real image needs it.
    The session exposes no writer of its own, by design, so the test reaches past
    it to the program.
    """
    session = analysis_engine().analyze_binary(stripped_firmware(CONTROLLER), analyze=False)
    assert isinstance(session, GhidraSession)
    try:
        program = session._program
        transaction = program.startTransaction("plant a diagnostic")
        try:
            program.getBookmarkManager().setBookmark(
                program.getImageBase(), "Error", "Bad Instruction", "could not disassemble"
            )
        finally:
            program.endTransaction(transaction, True)

        warnings = [
            item for item in session.analysis_warnings() if item.code == WARNING_ENGINE_DIAGNOSTIC
        ]
    finally:
        session.close()

    assert len(warnings) == 1
    assert warnings[0].severity == "error"
    assert warnings[0].address == 0x100000000
    assert warnings[0].message == "Bad Instruction - could not disassemble"


def test_warnings_are_stable_across_calls() -> None:
    session = open_sample(LOOKUP_1D)

    assert session.analysis_warnings() == session.analysis_warnings()


def test_a_clean_import_still_reports_what_it_could_not_account_for() -> None:
    """Silence would be a claim. Every run says something about its own limits."""
    warnings = open_sample(LOOKUP_1D).analysis_warnings()

    assert warnings
    assert all(item.severity in {"error", "warning", "info"} for item in warnings)
    assert all(item.code and item.message for item in warnings)


def test_decompilation_is_repeatable_for_every_discovered_function() -> None:
    session = open_sample(CONTROLLER)
    functions = session.export().functions

    results = [session.decompile_function(function.id) for function in functions]

    assert len(results) == len(ground_truth_symbols(CONTROLLER))
    assert all(item.success for item in results)
    assert [item.text for item in results] == [
        session.decompile_function(function.id).text for function in functions
    ]


# --- deterministic failure ---


def test_an_unknown_function_address_raises_a_typed_error() -> None:
    with pytest.raises(UnknownFunctionError):
        open_sample(CONTROLLER).get_function(0x100000F41)


@pytest.mark.parametrize(
    "start,length", [(0xDEAD0000, 16), (0x100000F40, 1_000_000), (0x100000F40, 0)]
)
def test_bad_read_requests_are_rejected_with_a_typed_error(start: int, length: int) -> None:
    with pytest.raises(InvalidRequestError):
        open_sample(CONTROLLER).read_bytes(start, length)


@pytest.mark.parametrize("limit,offset", [(0, 0), (MAX_RESULTS + 1, 0), (10, -1)])
def test_bad_paging_requests_are_rejected_with_a_typed_error(limit: int, offset: int) -> None:
    with pytest.raises(InvalidRequestError):
        open_sample(CONTROLLER).list_functions(limit=limit, offset=offset)


def test_a_non_positive_decompiler_timeout_is_rejected() -> None:
    session = open_sample(CONTROLLER)
    function = session.export().functions[0]

    with pytest.raises(InvalidRequestError):
        session.decompile_function(function.id, timeout_seconds=0)


def test_a_file_ghidra_cannot_load_raises_an_analysis_error_not_a_java_trace(
    tmp_path: Path,
) -> None:
    junk = tmp_path / "not-firmware.txt"
    junk.write_text("this is plainly not firmware\n" * 8, encoding="utf-8")

    with pytest.raises(AnalysisError, match="could not analyze"):
        analysis_engine().analyze_binary(junk)


def test_a_closed_session_refuses_every_further_request() -> None:
    session = analysis_engine().analyze_binary(stripped_firmware(CONTROLLER), analyze=False)
    session.close()
    session.close()  # must tolerate a repeat call

    with pytest.raises(AnalysisError, match="closed"):
        session.analysis_warnings()
    with pytest.raises(AnalysisError, match="closed"):
        session.list_functions()
