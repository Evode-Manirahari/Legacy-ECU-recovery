"""Engine-independent static-analysis interface.

`analyze_binary` opens a session; every other capability is a method on that
session. Splitting them this way keeps the expensive import-and-analyze step
explicit and gives the session a defined lifetime, which matters because the
Ghidra implementation holds a JVM-backed project open.

The bounds defined here are deliberate. An agent must never be able to request
an unbounded response, so the limits live at the interface rather than inside a
single engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType

from .models import (
    AnalysisExport,
    ArchitectureConfig,
    ByteWindow,
    ConstantMatch,
    CrossReference,
    DecompilerResult,
    DisassemblyResult,
    FunctionRecord,
    MemoryRegion,
    ProgramSummary,
    StringRecord,
)

MAX_READ_BYTES = 4096
MAX_INSTRUCTIONS = 4096
MAX_RESULTS = 1000
DEFAULT_PAGE_SIZE = 100


class AnalysisError(RuntimeError):
    """Any failure raised by a static-analysis engine."""


class EngineUnavailableError(AnalysisError):
    """The engine or one of its runtime dependencies is not installed."""


class UnknownFunctionError(AnalysisError):
    """A function id or address does not resolve to an analyzed function."""


class InvalidRequestError(AnalysisError):
    """Caller-supplied arguments were out of range or malformed."""


class StaticAnalysisSession(ABC):
    """One opened program. Not safe to share across threads."""

    @property
    @abstractmethod
    def program(self) -> ProgramSummary:
        """What the engine loaded, including values it detected itself."""

    @abstractmethod
    def list_functions(
        self, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0
    ) -> tuple[FunctionRecord, ...]:
        """Return functions ordered by entry address."""

    @abstractmethod
    def function_count(self) -> int:
        """Total analyzed functions, so a caller can page without guessing."""

    @abstractmethod
    def get_function(self, address: int | str) -> FunctionRecord:
        """Resolve one function by entry address or function id."""

    @abstractmethod
    def get_disassembly(self, function_id: str, limit: int = MAX_INSTRUCTIONS) -> DisassemblyResult:
        """Return the instructions in a function's body."""

    @abstractmethod
    def decompile_function(self, function_id: str, timeout_seconds: int = 30) -> DecompilerResult:
        """Decompile one function. Failure is reported, not raised."""

    @abstractmethod
    def get_callers(self, function_id: str) -> tuple[FunctionRecord, ...]:
        """Functions that call this function."""

    @abstractmethod
    def get_callees(self, function_id: str) -> tuple[FunctionRecord, ...]:
        """Functions this function calls."""

    @abstractmethod
    def get_cross_references(
        self, address: int | str, limit: int = MAX_RESULTS
    ) -> tuple[CrossReference, ...]:
        """References that target the supplied address."""

    @abstractmethod
    def list_strings(
        self, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0, minimum_length: int = 4
    ) -> tuple[StringRecord, ...]:
        """Defined strings ordered by address."""

    @abstractmethod
    def list_memory_regions(self) -> tuple[MemoryRegion, ...]:
        """Loaded memory blocks ordered by start address."""

    @abstractmethod
    def read_bytes(self, start: int, length: int) -> ByteWindow:
        """Read initialized program bytes. Bounded by `MAX_READ_BYTES`."""

    @abstractmethod
    def search_constant(self, value: int, limit: int = MAX_RESULTS) -> tuple[ConstantMatch, ...]:
        """Find instruction operands equal to `value`."""

    @abstractmethod
    def close(self) -> None:
        """Release engine resources. Must tolerate repeat calls."""

    def export(self, include_decompilation: bool = False) -> AnalysisExport:
        """Collect a full, serializable snapshot of this session.

        Defined once here so every engine exports the same shape. Decompilation
        is opt-in because it is by far the slowest step.
        """
        functions = self.list_functions(limit=MAX_RESULTS)
        decompilations: tuple[DecompilerResult, ...] = ()
        if include_decompilation:
            decompilations = tuple(self.decompile_function(function.id) for function in functions)
        return AnalysisExport(
            program=self.program,
            memory_regions=self.list_memory_regions(),
            functions=functions,
            strings=self.list_strings(limit=MAX_RESULTS),
            decompilations=decompilations,
        )

    def __enter__(self) -> StaticAnalysisSession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class StaticAnalysisEngine(ABC):
    """Factory for sessions. One engine may open many programs in sequence."""

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this engine can run right now, without raising."""

    @abstractmethod
    def analyze_binary(
        self,
        path: str | Path,
        architecture: ArchitectureConfig | None = None,
        analyze: bool = True,
    ) -> StaticAnalysisSession:
        """Import a binary and run engine auto-analysis.

        The binary is treated strictly as data. Nothing here executes it.
        """


def validate_read_request(start: int, length: int) -> None:
    """Shared bounds check so every engine rejects the same requests."""
    if start < 0:
        raise InvalidRequestError("start address must not be negative")
    if length <= 0:
        raise InvalidRequestError("length must be positive")
    if length > MAX_READ_BYTES:
        raise InvalidRequestError(f"length {length} exceeds the {MAX_READ_BYTES} byte limit")


def validate_page(limit: int, offset: int) -> None:
    """Shared paging check so no caller can request an unbounded page."""
    if limit <= 0:
        raise InvalidRequestError("limit must be positive")
    if limit > MAX_RESULTS:
        raise InvalidRequestError(f"limit {limit} exceeds the {MAX_RESULTS} result cap")
    if offset < 0:
        raise InvalidRequestError("offset must not be negative")


def parse_address(address: int | str) -> int:
    """Accept an int, a `0x`-prefixed string, or a function id."""
    if isinstance(address, int):
        parsed = address
    else:
        try:
            parsed = int(address, 16 if address.lower().startswith("0x") else 0)
        except (AttributeError, ValueError) as error:
            raise InvalidRequestError(f"could not parse address {address!r}") from error
    if parsed < 0:
        raise InvalidRequestError("address must not be negative")
    return parsed
