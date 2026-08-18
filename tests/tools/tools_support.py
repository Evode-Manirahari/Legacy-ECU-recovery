"""Helpers for the tool-layer tests.

Named uniquely rather than `conftest` for the reason the other node test
directories record: pytest puts each test directory on `sys.path`, so a second
`conftest` shadows the root one and mypy rejects the duplicate module name.

The fake session matters more than it looks. Most of what this node promises -
paging, bounds, truncation flags, structured errors - is a property of the tool
layer, not of Ghidra, so it should be provable on a host with no Ghidra at all.
That keeps the guarantees under test in CI rather than only on a developer's
machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ecu_recovery.analysis.base import (
    MAX_INSTRUCTIONS,
    MAX_RESULTS,
    AnalysisError,
    StaticAnalysisSession,
)
from ecu_recovery.analysis.ghidra import GhidraEngine
from ecu_recovery.analysis.models import (
    AnalysisWarning,
    ArchitectureConfig,
    ByteWindow,
    ConstantMatch,
    CrossReference,
    DecompilerResult,
    DisassemblyResult,
    FunctionRecord,
    Instruction,
    MemoryRegion,
    ProgramSummary,
    StringRecord,
    function_id_for,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = PROJECT_ROOT / "samples" / "synthetic" / "binaries"
PIPELINE = "multi_function_pipeline_v1"


def ghidra_skip_reason() -> str | None:
    try:
        import pyghidra  # noqa: F401
    except ImportError:
        return "pyghidra is not installed; run `uv sync --extra ghidra`"
    if GhidraEngine().install_dir is None:
        return "no Ghidra installation found; set GHIDRA_INSTALL_DIR"
    return None


requires_ghidra = pytest.mark.skipif(
    ghidra_skip_reason() is not None, reason=ghidra_skip_reason() or ""
)


def stripped_firmware(sample_id: str = PIPELINE) -> Path:
    return SAMPLES / sample_id / "firmware.stripped"


def make_function(index: int) -> FunctionRecord:
    address = 0x1000 + index * 0x40
    return FunctionRecord(
        id=function_id_for(address),
        name=f"FUN_{address:x}",
        start_address=address,
        end_address=address + 0x3F,
        size=0x40,
        callers=(),
        callees=(),
    )


class FakeSession(StaticAnalysisSession):
    """A session with no engine behind it.

    Every knob a test needs is a constructor argument, so a test can ask for
    "a session with 250 functions" or "a session that raises" without a JVM.
    """

    def __init__(
        self,
        function_count: int = 5,
        *,
        raises: Exception | None = None,
        closed: bool = False,
        decompiled_text: str = "int f(void) { return 0; }",
        string_count: int = 3,
        constant_matches: int = 2,
    ) -> None:
        self._functions = tuple(make_function(index) for index in range(function_count))
        self._raises = raises
        self._closed = closed
        self._text = decompiled_text
        self._string_count = string_count
        self._constant_matches = constant_matches

    def _guard(self) -> None:
        if self._closed:
            raise AnalysisError("session is closed")
        if self._raises is not None:
            raise self._raises

    @property
    def program(self) -> ProgramSummary:
        return ProgramSummary(
            source_path="binaries/fake/firmware.stripped",
            program_name="firmware.stripped",
            language_id="x86:LE:64:default",
            compiler_spec_id="gcc",
            image_base=0x1000,
            executable_format="Mac OS X Mach-O",
            executable_sha256="ab" * 32,
            engine="fake",
            engine_version="0",
            requested=ArchitectureConfig(),
            processor="x86",
            endian="little",
            address_size_bits=64,
            pointer_size_bytes=8,
            entry_points=(0x1000,),
        )

    def list_functions(self, limit: int = 100, offset: int = 0) -> tuple[FunctionRecord, ...]:
        self._guard()
        return self._functions[offset : offset + limit]

    def function_count(self) -> int:
        self._guard()
        return len(self._functions)

    def get_function(self, address: int | str) -> FunctionRecord:
        self._guard()
        for function in self._functions:
            if function.id == address or function.start_address == address:
                return function
        from ecu_recovery.analysis.base import UnknownFunctionError

        raise UnknownFunctionError(f"no function begins at {address!r}")

    def get_disassembly(self, function_id: str, limit: int = MAX_INSTRUCTIONS) -> DisassemblyResult:
        self._guard()
        instructions = tuple(
            Instruction(0x1000 + index, "NOP", "", "90") for index in range(min(limit, 10))
        )
        return DisassemblyResult(function_id, instructions, truncated=limit < 10)

    def decompile_function(self, function_id: str, timeout_seconds: int = 30) -> DecompilerResult:
        self._guard()
        return DecompilerResult(function_id, self._text, True)

    def get_callers(self, function_id: str) -> tuple[FunctionRecord, ...]:
        self._guard()
        return self._functions[:3]

    def get_callees(self, function_id: str) -> tuple[FunctionRecord, ...]:
        self._guard()
        return self._functions[:3]

    def get_cross_references(
        self, address: int | str, limit: int = MAX_RESULTS
    ) -> tuple[CrossReference, ...]:
        self._guard()
        return tuple(
            CrossReference(0x2000 + index, 0x1000, "CALL", True) for index in range(min(limit, 4))
        )

    def list_strings(
        self, limit: int = 100, offset: int = 0, minimum_length: int = 4
    ) -> tuple[StringRecord, ...]:
        self._guard()
        items = tuple(
            StringRecord(0x3000 + index, f"string{index}", 8, "string")
            for index in range(self._string_count)
        )
        return items[offset : offset + limit]

    def list_memory_regions(self) -> tuple[MemoryRegion, ...]:
        self._guard()
        return (
            MemoryRegion("__text", 0x1000, 0x1FFF, True, False, True, True),
            MemoryRegion("__const", 0x2000, 0x20FF, True, False, False, True),
        )

    def read_bytes(self, start: int, length: int) -> ByteWindow:
        self._guard()
        return ByteWindow(start, length, "90" * length)

    def search_constant(self, value: int, limit: int = MAX_RESULTS) -> tuple[ConstantMatch, ...]:
        self._guard()
        return tuple(
            ConstantMatch(0x1000 + index, value, "operand", operand_index=0, mnemonic="MOV")
            for index in range(min(limit, self._constant_matches))
        )

    def analysis_warnings(self) -> tuple[AnalysisWarning, ...]:
        self._guard()
        return (AnalysisWarning("uncovered-executable-bytes", "padding", "info", 0x1FF0),)

    def close(self) -> None:
        self._closed = True


def fake_context(**kwargs: Any) -> Any:
    from ecu_recovery.tools import ToolContext

    return ToolContext(session=FakeSession(**kwargs))
