"""Doubles for the agent tests.

No provider SDK exists in this project and none is added here. The model
boundary is one method, so a double is a few lines, and every property this node
claims is provable without a network call or an API key.

The session double is the one from the tool tests in shape: the agent reaches
the system only through `ToolRegistry`, so a fake session is enough to drive the
whole path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ecu_recovery.agent import ModelRequest, ModelResponse, ModelUnavailableError
from ecu_recovery.analysis.base import (
    MAX_INSTRUCTIONS,
    MAX_RESULTS,
    AnalysisError,
    StaticAnalysisSession,
)
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
from ecu_recovery.tools import ToolContext

SUBJECT = function_id_for(0x1000)


@dataclass
class ScriptedProvider:
    """Returns whatever the test tells it to, and records what it was asked."""

    reply: str = '{"claims": []}'
    name: str = "scripted"
    model: str = "double"
    raises: Exception | None = None
    requests: list[ModelRequest] = field(default_factory=list)

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.raises is not None:
            raise self.raises
        return ModelResponse(text=self.reply, provider=self.name, model=self.model)


def unavailable_provider() -> ScriptedProvider:
    return ScriptedProvider(raises=ModelUnavailableError("no key configured"))


class FakeSession(StaticAnalysisSession):
    """Enough of a session to drive the tool layer, with no engine behind it."""

    def __init__(self, *, decompiles: bool = True, failing_tool: str | None = None) -> None:
        self._decompiles = decompiles
        self._failing_tool = failing_tool
        self._functions = (
            FunctionRecord(
                id=SUBJECT,
                name="FUN_00001000",
                start_address=0x1000,
                end_address=0x103F,
                size=0x40,
                callers=(function_id_for(0x2000),),
                callees=(function_id_for(0x3000),),
            ),
            FunctionRecord(function_id_for(0x2000), "FUN_00002000", 0x2000, 0x203F, 0x40),
            FunctionRecord(function_id_for(0x3000), "FUN_00003000", 0x3000, 0x303F, 0x40),
        )

    def _guard(self, tool: str) -> None:
        if self._failing_tool == tool:
            raise AnalysisError(f"{tool} is unavailable in this fixture")

    @property
    def program(self) -> ProgramSummary:
        return ProgramSummary(
            source_path="binaries/fake/firmware.stripped",
            program_name="firmware.stripped",
            language_id="PowerPC:BE:32:default",
            compiler_spec_id="default",
            image_base=0x1000,
            executable_format="Raw Binary",
            executable_sha256="cd" * 32,
            engine="fake",
            engine_version="0",
            requested=ArchitectureConfig(),
            processor="PowerPC",
            endian="big",
            address_size_bits=32,
            pointer_size_bytes=4,
            entry_points=(0x1000,),
        )

    def list_functions(self, limit: int = 100, offset: int = 0) -> tuple[FunctionRecord, ...]:
        return self._functions[offset : offset + limit]

    def function_count(self) -> int:
        self._guard("binary_summary")
        return len(self._functions)

    def get_function(self, address: int | str) -> FunctionRecord:
        for function in self._functions:
            if function.id == address or function.start_address == address:
                return function
        from ecu_recovery.analysis.base import UnknownFunctionError

        raise UnknownFunctionError(f"no function begins at {address!r}")

    def get_disassembly(self, function_id: str, limit: int = MAX_INSTRUCTIONS) -> DisassemblyResult:
        self._guard("inspect_function")
        instructions = tuple(
            Instruction(0x1000 + index * 4, "addi", "r3,r3,1", "38630001")
            for index in range(min(limit, 4))
        )
        return DisassemblyResult(function_id, instructions, truncated=limit < 4)

    def decompile_function(self, function_id: str, timeout_seconds: int = 30) -> DecompilerResult:
        if not self._decompiles:
            return DecompilerResult(function_id, "", False, ("timed out",))
        return DecompilerResult(function_id, "int f(int a){return a+1;}", True)

    def get_callers(self, function_id: str) -> tuple[FunctionRecord, ...]:
        self._guard("get_callers")
        return (self._functions[1],)

    def get_callees(self, function_id: str) -> tuple[FunctionRecord, ...]:
        return (self._functions[2],)

    def get_cross_references(
        self, address: int | str, limit: int = MAX_RESULTS
    ) -> tuple[CrossReference, ...]:
        return (CrossReference(0x2000, 0x1000, "CALL", True),)

    def list_strings(
        self, limit: int = 100, offset: int = 0, minimum_length: int = 4
    ) -> tuple[StringRecord, ...]:
        return ()

    def list_memory_regions(self) -> tuple[MemoryRegion, ...]:
        return (MemoryRegion("ROM", 0x1000, 0x1FFF, True, False, True, True),)

    def read_bytes(self, start: int, length: int) -> ByteWindow:
        return ByteWindow(start, length, "00" * length)

    def search_constant(self, value: int, limit: int = MAX_RESULTS) -> tuple[ConstantMatch, ...]:
        return ()

    def analysis_warnings(self) -> tuple[AnalysisWarning, ...]:
        return (AnalysisWarning("uncovered-executable-bytes", "padding", "info", 0x1FF0),)

    def close(self) -> None:
        return None


def fake_context(**kwargs: object) -> ToolContext:
    return ToolContext(session=FakeSession(**kwargs))  # type: ignore[arg-type]
