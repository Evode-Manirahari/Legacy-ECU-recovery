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
    AnalysisWarning,
    ArchitectureConfig,
    BinaryAnalysis,
    ByteWindow,
    ConstantMatch,
    CrossReference,
    DecompilerResult,
    DisassemblyResult,
    FunctionRecord,
    MemoryRegion,
    ProgramSummary,
    StringRecord,
    sorted_warnings,
)

MAX_READ_BYTES = 4096
MAX_INSTRUCTIONS = 4096
MAX_RESULTS = 1000
DEFAULT_PAGE_SIZE = 100

#: An export pages through the engine rather than asking for everything at
#: once, but it still needs an end. These are the points past which an export
#: stops and says so instead of growing without limit.
MAX_EXPORT_FUNCTIONS = 20_000
MAX_EXPORT_STRINGS = 5_000

# Warning codes are part of the interface: a consumer matches on the code, not
# on the prose, so the prose can be improved without breaking anyone.
WARNING_AUTO_ANALYSIS_SKIPPED = "auto-analysis-skipped"
WARNING_NO_FUNCTIONS = "no-functions-discovered"
WARNING_IMAGE_BASE_OVERRIDDEN = "image-base-overridden"
WARNING_LANGUAGE_DECLARED = "language-declared"
WARNING_COMPILER_SPEC_DECLARED = "compiler-spec-declared"
WARNING_UNINITIALIZED_BLOCK = "uninitialized-memory-block"
WARNING_UNCOVERED_CODE_BYTES = "uncovered-executable-bytes"
WARNING_ENGINE_DIAGNOSTIC = "engine-diagnostic"
WARNING_DECOMPILATION_FAILED = "decompilation-failed"
WARNING_FUNCTIONS_TRUNCATED = "function-listing-truncated"
WARNING_STRINGS_TRUNCATED = "string-listing-truncated"


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
        """Find semantically relevant uses of `value`.

        Two kinds of evidence qualify: a scalar operand of a decoded
        instruction, and a defined data object that code refers to. A raw byte
        sequence that happens to equal the value is not a use of it and must
        never be reported as one.
        """

    @abstractmethod
    def analysis_warnings(self) -> tuple[AnalysisWarning, ...]:
        """Everything the engine could not establish about this program.

        Reporting an empty tuple is a claim, so an engine must compute this
        rather than default it. Repeat calls must return the same result.
        """

    @abstractmethod
    def close(self) -> None:
        """Release engine resources. Must tolerate repeat calls."""

    def export(self, include_decompilation: bool = False) -> BinaryAnalysis:
        """Collect a full, serializable snapshot of this session.

        Defined once here so every engine exports the same shape. Decompilation
        is opt-in because it is by far the slowest step.

        Paging is done here rather than in a single oversized request: a real
        firmware image can hold more functions than one page allows, and a
        silently short list would read as a discovery failure downstream.
        """
        functions, functions_truncated = self._page_functions()
        strings, strings_truncated = self._page_strings()
        warnings = list(self.analysis_warnings())
        if functions_truncated:
            warnings.append(
                AnalysisWarning(
                    code=WARNING_FUNCTIONS_TRUNCATED,
                    message=(
                        f"stopped after {MAX_EXPORT_FUNCTIONS} functions; the export is incomplete"
                    ),
                )
            )
        if strings_truncated:
            warnings.append(
                AnalysisWarning(
                    code=WARNING_STRINGS_TRUNCATED,
                    message=f"stopped after {MAX_EXPORT_STRINGS} strings; the export is incomplete",
                    severity="info",
                )
            )
        decompilations: tuple[DecompilerResult, ...] = ()
        if include_decompilation:
            decompilations = tuple(self.decompile_function(function.id) for function in functions)
            warnings.extend(
                AnalysisWarning(
                    code=WARNING_DECOMPILATION_FAILED,
                    message="; ".join(item.warnings) or "decompiler produced no output",
                    address=int(item.function_id, 16),
                )
                for item in decompilations
                if not item.success
            )
        return BinaryAnalysis(
            program=self.program,
            memory_regions=self.list_memory_regions(),
            functions=functions,
            strings=strings,
            decompilations=decompilations,
            analysis_warnings=sorted_warnings(warnings),
        )

    def _page_functions(self) -> tuple[tuple[FunctionRecord, ...], bool]:
        collected: list[FunctionRecord] = []
        offset = 0
        while len(collected) < MAX_EXPORT_FUNCTIONS:
            page = self.list_functions(limit=MAX_RESULTS, offset=offset)
            if not page:
                return tuple(collected), False
            collected.extend(page)
            offset += len(page)
            if len(page) < MAX_RESULTS:
                return tuple(collected), False
        return tuple(collected[:MAX_EXPORT_FUNCTIONS]), True

    def _page_strings(self) -> tuple[tuple[StringRecord, ...], bool]:
        collected: list[StringRecord] = []
        offset = 0
        while len(collected) < MAX_EXPORT_STRINGS:
            page = self.list_strings(limit=MAX_RESULTS, offset=offset)
            if not page:
                return tuple(collected), False
            collected.extend(page)
            offset += len(page)
            if len(page) < MAX_RESULTS:
                return tuple(collected), False
        return tuple(collected[:MAX_EXPORT_STRINGS]), True

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
