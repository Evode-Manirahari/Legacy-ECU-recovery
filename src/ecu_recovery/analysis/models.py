"""Plain analysis records shared by every static-analysis engine.

Nothing in this module may import an engine. These records are the stable
vocabulary the rest of the system reasons about, so a later engine swap does not
ripple into storage, the agent, or reporting.

Addresses are stored as integers because callers compare and sort them. They are
rendered as hex strings during serialization because a human reads the exported
JSON alongside a disassembler.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

#: Ordered most to least severe. The order is the sort order, so a reader sees
#: what broke before what merely happened.
WARNING_SEVERITIES = ("error", "warning", "info")


def render_address(address: int) -> str:
    """Render an address the way a disassembler displays it."""
    return f"0x{address:08x}"


def function_id_for(entry_address: int) -> str:
    """Derive the stable identifier for a function from its entry address.

    Entry address is the only function property that survives stripping, so it
    is the identity. Ghidra's `FUN_*` label is a display name, not an identity.
    """
    return render_address(entry_address)


def address_of_function_id(function_id: str) -> int:
    """Invert `function_id_for`. Ids are the only handle the export carries."""
    return int(function_id, 16)


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
class AnalysisWarning:
    """Something the engine could not do, or did on the investigator's word.

    Warnings are facts about the run, not judgements about the firmware. They
    exist so a downstream reader never mistakes "the tool did not look" for "the
    tool looked and found nothing".
    """

    code: str
    message: str
    severity: str = "warning"
    address: int | None = None

    @property
    def sort_key(self) -> tuple[int, str, int, str]:
        """Deterministic ordering: severity, then code, then address."""
        rank = (
            WARNING_SEVERITIES.index(self.severity)
            if self.severity in WARNING_SEVERITIES
            else len(WARNING_SEVERITIES)
        )
        return (rank, self.code, -1 if self.address is None else self.address, self.message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "address": None if self.address is None else render_address(self.address),
        }


def sorted_warnings(warnings: Iterable[AnalysisWarning]) -> tuple[AnalysisWarning, ...]:
    """Order warnings and drop exact duplicates, so two runs agree byte for byte."""
    return tuple(sorted(dict.fromkeys(warnings), key=lambda item: item.sort_key))


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

    def contains(self, address: int) -> bool:
        return self.start_address <= address <= self.end_address

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
class CallEdge:
    """One caller-to-callee relationship, deduplicated.

    A function that calls the same callee from four sites still produces one
    edge. Evaluation compares address pairs, so repeated call sites would
    otherwise inflate both sides of the comparison.
    """

    caller_id: str
    callee_id: str
    caller_address: int
    callee_address: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "caller_id": self.caller_id,
            "callee_id": self.callee_id,
            "caller_address": render_address(self.caller_address),
            "callee_address": render_address(self.callee_address),
        }


def call_edges_from(functions: Iterable[FunctionRecord]) -> tuple[CallEdge, ...]:
    """Derive the call graph from function records.

    Derived rather than stored: `FunctionRecord.callees` is the single source of
    truth, so an export can never disagree with itself.
    """
    edges = {
        CallEdge(
            caller_id=function.id,
            callee_id=callee_id,
            caller_address=function.start_address,
            callee_address=address_of_function_id(callee_id),
        )
        for function in functions
        for callee_id in function.callees
    }
    return tuple(sorted(edges, key=lambda edge: (edge.caller_address, edge.callee_address)))


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


#: A scalar the disassembler decoded inside an instruction.
CONSTANT_KIND_OPERAND = "operand"
#: A defined data object that at least one instruction refers to.
CONSTANT_KIND_DATA = "data"


@dataclass(frozen=True)
class ConstantMatch:
    """Semantically relevant evidence that a program uses a value.

    Two kinds of evidence qualify, and only two:

    * `operand` - the value is a scalar operand of a decoded instruction;
    * `data` - the value is a defined data object that code refers to, which is
      how a compiler emits a calibration table.

    A byte sequence that merely equals the value somewhere in the image is not
    evidence. Mach-O headers and link-edit tables are full of small integers,
    and counting them would manufacture recoveries that no instruction supports.
    `reference_count` is carried so a consumer can see the strength of the
    evidence rather than take the classification on trust.
    """

    address: int
    value: int
    kind: str = CONSTANT_KIND_OPERAND
    function_id: str | None = None
    operand_index: int | None = None
    mnemonic: str | None = None
    data_type: str | None = None
    block_name: str | None = None
    reference_count: int = 0

    @property
    def sort_key(self) -> tuple[int, str, int]:
        return (self.address, self.kind, -1 if self.operand_index is None else self.operand_index)

    def as_dict(self) -> dict[str, Any]:
        return {
            "address": render_address(self.address),
            "value": self.value,
            "kind": self.kind,
            "function_id": self.function_id,
            "operand_index": self.operand_index,
            "mnemonic": self.mnemonic,
            "data_type": self.data_type,
            "block_name": self.block_name,
            "reference_count": self.reference_count,
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
    # Detected architecture facts. Defaulted because they were added after the
    # first export shape shipped; an engine that cannot report one leaves it as
    # the default rather than guessing.
    processor: str = "unknown"
    endian: str = "unknown"
    address_size_bits: int = 0
    pointer_size_bytes: int = 0
    entry_points: tuple[int, ...] = ()
    auto_analysis_ran: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "program_name": self.program_name,
            "language_id": self.language_id,
            "compiler_spec_id": self.compiler_spec_id,
            "processor": self.processor,
            "endian": self.endian,
            "address_size_bits": self.address_size_bits,
            "pointer_size_bytes": self.pointer_size_bytes,
            "image_base": render_address(self.image_base),
            "entry_points": [render_address(item) for item in self.entry_points],
            "executable_format": self.executable_format,
            "executable_sha256": self.executable_sha256,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "auto_analysis_ran": self.auto_analysis_ran,
            "requested": self.requested.as_dict(),
        }


@dataclass(frozen=True)
class BinaryAnalysis:
    """The complete serializable result of one analysis run.

    `schema_version` stays at 1: every change so far has added keys, and no
    consumer exists yet that could be broken by one. It moves when a key changes
    meaning or disappears.
    """

    program: ProgramSummary
    memory_regions: tuple[MemoryRegion, ...]
    functions: tuple[FunctionRecord, ...]
    strings: tuple[StringRecord, ...]
    decompilations: tuple[DecompilerResult, ...] = ()
    analysis_warnings: tuple[AnalysisWarning, ...] = ()

    @property
    def call_relationships(self) -> tuple[CallEdge, ...]:
        return call_edges_from(self.functions)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "program": self.program.as_dict(),
            "memory_regions": [region.as_dict() for region in self.memory_regions],
            "function_count": len(self.functions),
            "functions": [function.as_dict() for function in self.functions],
            "call_relationships": [edge.as_dict() for edge in self.call_relationships],
            "analysis_warnings": [item.as_dict() for item in self.analysis_warnings],
            "strings": [item.as_dict() for item in self.strings],
            "decompilations": [item.as_dict() for item in self.decompilations],
        }


#: The name this record shipped under before the node contract fixed
#: `BinaryAnalysis` as the required model name. Kept so pre-graph callers and
#: their regressions keep working.
AnalysisExport = BinaryAnalysis
