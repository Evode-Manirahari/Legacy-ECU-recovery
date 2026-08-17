"""Plain analysis records shared by every static-analysis engine.

Nothing in this module may import an engine. These records are the stable
vocabulary the rest of the system reasons about, so a later engine swap does not
ripple into storage, the agent, or reporting.

Addresses are stored as integers because callers compare and sort them. They are
rendered as hex strings during serialization because a human reads the exported
JSON alongside a disassembler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def render_address(address: int) -> str:
    """Render an address the way a disassembler displays it."""
    return f"0x{address:08x}"


def function_id_for(entry_address: int) -> str:
    """Derive the stable identifier for a function from its entry address.

    Entry address is the only function property that survives stripping, so it
    is the identity. Ghidra's `FUN_*` label is a display name, not an identity.
    """
    return render_address(entry_address)


@dataclass(frozen=True)
class ArchitectureConfig:
    """Investigator-supplied load configuration.

    Every field is optional. When a field is `None` the engine is permitted to
    detect it, and the detected value is reported back in `ProgramSummary` so a
    reader can tell a declared fact from a detected one.
    """

    language_id: str | None = None
    compiler_spec_id: str | None = None
    base_address: int | None = None
    processor_label: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "language_id": self.language_id,
            "compiler_spec_id": self.compiler_spec_id,
            "base_address": None
            if self.base_address is None
            else render_address(self.base_address),
            "processor_label": self.processor_label,
        }


@dataclass(frozen=True)
class MemoryRegion:
    name: str
    start_address: int
    end_address: int
    readable: bool
    writable: bool
    executable: bool
    initialized: bool

    @property
    def size(self) -> int:
        return self.end_address - self.start_address + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_address": render_address(self.start_address),
            "end_address": render_address(self.end_address),
            "size": self.size,
            "readable": self.readable,
            "writable": self.writable,
            "executable": self.executable,
            "initialized": self.initialized,
        }


@dataclass(frozen=True)
class FunctionRecord:
    """A function as the analysis layer sees it.

    `callers` and `callees` hold function ids rather than nested records so the
    graph stays acyclic when serialized and a caller can page through it.
    """

    id: str
    name: str
    start_address: int
    end_address: int
    size: int
    callers: tuple[str, ...] = ()
    callees: tuple[str, ...] = ()
    is_thunk: bool = False
    is_external: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start_address": render_address(self.start_address),
            "end_address": render_address(self.end_address),
            "size": self.size,
            "callers": list(self.callers),
            "callees": list(self.callees),
            "is_thunk": self.is_thunk,
            "is_external": self.is_external,
        }


@dataclass(frozen=True)
class Instruction:
    address: int
    mnemonic: str
    operands: str
    bytes_hex: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "address": render_address(self.address),
            "mnemonic": self.mnemonic,
            "operands": self.operands,
            "bytes": self.bytes_hex,
        }


@dataclass(frozen=True)
class DisassemblyResult:
    function_id: str
    instructions: tuple[Instruction, ...]
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "function_id": self.function_id,
            "instruction_count": len(self.instructions),
            "truncated": self.truncated,
            "instructions": [item.as_dict() for item in self.instructions],
        }


@dataclass(frozen=True)
class DecompilerResult:
    """Decompiler output plus why it failed, when it failed.

    A failed decompilation is a recorded result, not an exception. The agent must
    be able to reason about which functions the decompiler could not handle.
    """

    function_id: str
    text: str
    success: bool
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "function_id": self.function_id,
            "success": self.success,
            "warnings": list(self.warnings),
            "text": self.text,
        }


@dataclass(frozen=True)
class StringRecord:
    address: int
    value: str
    length: int
    encoding: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "address": render_address(self.address),
            "value": self.value,
            "length": self.length,
            "encoding": self.encoding,
        }


@dataclass(frozen=True)
class CrossReference:
    from_address: int
    to_address: int
    reference_type: str
    is_call: bool
    from_function_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "from_address": render_address(self.from_address),
            "to_address": render_address(self.to_address),
            "reference_type": self.reference_type,
            "is_call": self.is_call,
            "from_function_id": self.from_function_id,
        }


@dataclass(frozen=True)
class ConstantMatch:
    """A scalar operand equal to a searched value.

    Only instruction operands are searched. A byte pattern that happens to equal
    the value inside a data region is not a constant usage and would inflate the
    evidence base with coincidences.
    """

    address: int
    value: int
    operand_index: int
    mnemonic: str
    function_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "address": render_address(self.address),
            "value": self.value,
            "operand_index": self.operand_index,
            "mnemonic": self.mnemonic,
            "function_id": self.function_id,
        }


@dataclass(frozen=True)
class ByteWindow:
    start_address: int
    length: int
    data_hex: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_address": render_address(self.start_address),
            "length": self.length,
            "data": self.data_hex,
        }


@dataclass(frozen=True)
class ProgramSummary:
    """What the engine actually loaded, as opposed to what was requested."""

    source_path: str
    program_name: str
    language_id: str
    compiler_spec_id: str
    image_base: int
    executable_format: str
    executable_sha256: str
    engine: str
    engine_version: str
    requested: ArchitectureConfig = field(default_factory=ArchitectureConfig)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "program_name": self.program_name,
            "language_id": self.language_id,
            "compiler_spec_id": self.compiler_spec_id,
            "image_base": render_address(self.image_base),
            "executable_format": self.executable_format,
            "executable_sha256": self.executable_sha256,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "requested": self.requested.as_dict(),
        }


@dataclass(frozen=True)
class AnalysisExport:
    """The complete serializable result of one analysis run."""

    program: ProgramSummary
    memory_regions: tuple[MemoryRegion, ...]
    functions: tuple[FunctionRecord, ...]
    strings: tuple[StringRecord, ...]
    decompilations: tuple[DecompilerResult, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "program": self.program.as_dict(),
            "memory_regions": [region.as_dict() for region in self.memory_regions],
            "function_count": len(self.functions),
            "functions": [function.as_dict() for function in self.functions],
            "strings": [item.as_dict() for item in self.strings],
            "decompilations": [item.as_dict() for item in self.decompilations],
        }
