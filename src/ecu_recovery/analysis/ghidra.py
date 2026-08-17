"""PyGhidra-backed static analysis.

This module is the only place allowed to touch Ghidra's Java API. Everything it
returns is a plain record from `analysis.models`, so a Java object can never
reach storage, the agent, or a report.

Two import rules keep this file usable on a host without Ghidra:

1. `pyghidra` is imported inside functions, never at module scope, so `doctor`
   can import the discovery helper while Ghidra is missing.
2. `import ghidra.*` is only legal after `pyghidra.start()`, which is why those
   imports sit inside `_load_program`.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from .base import (
    DEFAULT_PAGE_SIZE,
    MAX_INSTRUCTIONS,
    MAX_RESULTS,
    AnalysisError,
    EngineUnavailableError,
    InvalidRequestError,
    StaticAnalysisEngine,
    StaticAnalysisSession,
    UnknownFunctionError,
    parse_address,
    validate_page,
    validate_read_request,
)
from .models import (
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

ENGINE_NAME = "ghidra"

#: Homebrew and the official archive install Ghidra in different shapes. Both
#: put the application root where `Ghidra/application.properties` is readable.
_INSTALL_HINTS = (
    "/usr/local/opt/ghidra/libexec",
    "/opt/homebrew/opt/ghidra/libexec",
    "/opt/ghidra",
)


def _looks_like_ghidra_install(candidate: Path) -> bool:
    return (candidate / "Ghidra" / "application.properties").is_file()


def find_ghidra_install_dir() -> Path | None:
    """Locate a Ghidra installation without importing PyGhidra.

    `GHIDRA_INSTALL_DIR` wins because an investigator may need to pin a specific
    Ghidra version for a reproducible run.
    """
    for variable in ("GHIDRA_INSTALL_DIR", "GHIDRA_HOME"):
        configured = os.environ.get(variable)
        if configured:
            candidate = Path(configured).expanduser()
            if _looks_like_ghidra_install(candidate):
                return candidate.resolve()
    for hint in _INSTALL_HINTS:
        candidate = Path(hint)
        if _looks_like_ghidra_install(candidate):
            return candidate.resolve()
    launcher = shutil.which("ghidraRun") or shutil.which("pyghidraRun")
    if launcher:
        # Homebrew ships `bin/ghidraRun` as a shim beside `libexec/`.
        for parent in Path(launcher).resolve().parents:
            if _looks_like_ghidra_install(parent):
                return parent
            if _looks_like_ghidra_install(parent / "libexec"):
                return (parent / "libexec").resolve()
    return None


def read_ghidra_version(install_dir: Path) -> str:
    """Read the installed Ghidra version so every export records its engine."""
    properties = install_dir / "Ghidra" / "application.properties"
    try:
        for line in properties.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "application.version":
                return value.strip()
    except OSError:
        pass
    return "unknown"


def _java_bytes_to_hex(raw: Any) -> str:
    """Convert a Java `byte[]` to hex. Java bytes are signed; mask them."""
    return bytes(int(item) & 0xFF for item in raw).hex()


class GhidraSession(StaticAnalysisSession):
    """One program held open inside the Ghidra JVM."""

    def __init__(
        self,
        flat: Any,
        stack: ExitStack,
        source_path: Path,
        requested: ArchitectureConfig,
        engine_version: str,
    ) -> None:
        self._stack = stack
        self._flat = flat
        self._program: Any = flat.getCurrentProgram()
        self._listing: Any = self._program.getListing()
        self._function_manager: Any = self._program.getFunctionManager()
        self._closed = False
        self._summary = ProgramSummary(
            source_path=str(source_path),
            program_name=str(self._program.getName()),
            language_id=str(self._program.getLanguageID()),
            compiler_spec_id=str(self._program.getCompilerSpec().getCompilerSpecID()),
            image_base=int(self._program.getImageBase().getOffset()),
            executable_format=str(self._program.getExecutableFormat()),
            executable_sha256=str(self._program.getExecutableSHA256()),
            engine=ENGINE_NAME,
            engine_version=engine_version,
            requested=requested,
        )

    @property
    def program(self) -> ProgramSummary:
        return self._summary

    def _require_open(self) -> None:
        if self._closed:
            raise AnalysisError("session is closed")

    def _address(self, value: int) -> Any:
        return self._program.getAddressFactory().getDefaultAddressSpace().getAddress(value)

    def _ordered_functions(self) -> list[Any]:
        return list(self._function_manager.getFunctions(True))

    def _to_record(self, function: Any) -> FunctionRecord:
        body = function.getBody()
        entry = int(function.getEntryPoint().getOffset())
        maximum = body.getMaxAddress()
        end = int(maximum.getOffset()) if maximum is not None else entry
        return FunctionRecord(
            id=function_id_for(entry),
            name=str(function.getName()),
            start_address=entry,
            end_address=end,
            size=int(body.getNumAddresses()),
            callers=tuple(
                sorted(
                    function_id_for(int(item.getEntryPoint().getOffset()))
                    for item in function.getCallingFunctions(None)
                )
            ),
            callees=tuple(
                sorted(
                    function_id_for(int(item.getEntryPoint().getOffset()))
                    for item in function.getCalledFunctions(None)
                )
            ),
            is_thunk=bool(function.isThunk()),
            is_external=bool(function.isExternal()),
        )

    def _resolve(self, function_id: str | int) -> Any:
        address = parse_address(function_id)
        function = self._function_manager.getFunctionAt(self._address(address))
        if function is None:
            raise UnknownFunctionError(f"no function begins at {function_id!r}")
        return function

    def function_count(self) -> int:
        self._require_open()
        return int(self._function_manager.getFunctionCount())

    def list_functions(
        self, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0
    ) -> tuple[FunctionRecord, ...]:
        self._require_open()
        validate_page(limit, offset)
        window = self._ordered_functions()[offset : offset + limit]
        return tuple(self._to_record(function) for function in window)

    def get_function(self, address: int | str) -> FunctionRecord:
        self._require_open()
        return self._to_record(self._resolve(address))

    def get_disassembly(self, function_id: str, limit: int = MAX_INSTRUCTIONS) -> DisassemblyResult:
        self._require_open()
        if limit <= 0 or limit > MAX_INSTRUCTIONS:
            raise InvalidRequestError(f"limit must be between 1 and {MAX_INSTRUCTIONS}")
        function = self._resolve(function_id)
        instructions: list[Instruction] = []
        truncated = False
        for item in self._listing.getInstructions(function.getBody(), True):
            if len(instructions) >= limit:
                truncated = True
                break
            operands = ", ".join(
                str(item.getDefaultOperandRepresentation(index))
                for index in range(int(item.getNumOperands()))
            )
            instructions.append(
                Instruction(
                    address=int(item.getAddress().getOffset()),
                    mnemonic=str(item.getMnemonicString()),
                    operands=operands,
                    bytes_hex=_java_bytes_to_hex(item.getBytes()),
                )
            )
        return DisassemblyResult(
            function_id=function_id_for(int(function.getEntryPoint().getOffset())),
            instructions=tuple(instructions),
            truncated=truncated,
        )

    def decompile_function(self, function_id: str, timeout_seconds: int = 30) -> DecompilerResult:
        self._require_open()
        if timeout_seconds <= 0:
            raise InvalidRequestError("timeout_seconds must be positive")
        from ghidra.app.decompiler import DecompInterface
        from ghidra.util.task import ConsoleTaskMonitor

        function = self._resolve(function_id)
        resolved_id = function_id_for(int(function.getEntryPoint().getOffset()))
        interface = DecompInterface()
        try:
            interface.openProgram(self._program)
            result = interface.decompileFunction(function, timeout_seconds, ConsoleTaskMonitor())
            message = str(result.getErrorMessage() or "").strip()
            if not result.decompileCompleted():
                return DecompilerResult(
                    function_id=resolved_id,
                    text="",
                    success=False,
                    warnings=(message or "decompilation did not complete",),
                )
            decompiled = result.getDecompiledFunction()
            return DecompilerResult(
                function_id=resolved_id,
                text=str(decompiled.getC()),
                success=True,
                warnings=(message,) if message else (),
            )
        finally:
            interface.dispose()

    def get_callers(self, function_id: str) -> tuple[FunctionRecord, ...]:
        self._require_open()
        function = self._resolve(function_id)
        callers = sorted(
            function.getCallingFunctions(None),
            key=lambda item: int(item.getEntryPoint().getOffset()),
        )
        return tuple(self._to_record(item) for item in callers)

    def get_callees(self, function_id: str) -> tuple[FunctionRecord, ...]:
        self._require_open()
        function = self._resolve(function_id)
        callees = sorted(
            function.getCalledFunctions(None),
            key=lambda item: int(item.getEntryPoint().getOffset()),
        )
        return tuple(self._to_record(item) for item in callees)

    def get_cross_references(
        self, address: int | str, limit: int = MAX_RESULTS
    ) -> tuple[CrossReference, ...]:
        self._require_open()
        validate_page(limit, 0)
        target = parse_address(address)
        manager = self._program.getReferenceManager()
        references: list[CrossReference] = []
        for reference in manager.getReferencesTo(self._address(target)):
            if len(references) >= limit:
                break
            source = int(reference.getFromAddress().getOffset())
            containing = self._function_manager.getFunctionContaining(reference.getFromAddress())
            reference_type = reference.getReferenceType()
            references.append(
                CrossReference(
                    from_address=source,
                    to_address=int(reference.getToAddress().getOffset()),
                    reference_type=str(reference_type),
                    is_call=bool(reference_type.isCall()),
                    from_function_id=(
                        None
                        if containing is None
                        else function_id_for(int(containing.getEntryPoint().getOffset()))
                    ),
                )
            )
        references.sort(key=lambda item: item.from_address)
        return tuple(references)

    def list_strings(
        self, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0, minimum_length: int = 4
    ) -> tuple[StringRecord, ...]:
        self._require_open()
        validate_page(limit, offset)
        if minimum_length < 1:
            raise InvalidRequestError("minimum_length must be positive")
        collected: list[StringRecord] = []
        seen = 0
        for data in self._listing.getDefinedData(True):
            if not data.hasStringValue():
                continue
            value = str(data.getValue())
            if len(value) < minimum_length:
                continue
            seen += 1
            if seen <= offset:
                continue
            collected.append(
                StringRecord(
                    address=int(data.getAddress().getOffset()),
                    value=value,
                    length=int(data.getLength()),
                    encoding=str(data.getDataType().getName()),
                )
            )
            if len(collected) >= limit:
                break
        return tuple(collected)

    def list_memory_regions(self) -> tuple[MemoryRegion, ...]:
        self._require_open()
        regions = [
            MemoryRegion(
                name=str(block.getName()),
                start_address=int(block.getStart().getOffset()),
                end_address=int(block.getEnd().getOffset()),
                readable=bool(block.isRead()),
                writable=bool(block.isWrite()),
                executable=bool(block.isExecute()),
                initialized=bool(block.isInitialized()),
            )
            for block in self._program.getMemory().getBlocks()
        ]
        regions.sort(key=lambda region: region.start_address)
        return tuple(regions)

    def read_bytes(self, start: int, length: int) -> ByteWindow:
        self._require_open()
        validate_read_request(start, length)
        from jpype import JArray, JByte

        buffer = JArray(JByte)(length)
        try:
            read = int(self._program.getMemory().getBytes(self._address(start), buffer))
        except Exception as error:  # noqa: BLE001 - Java raises unmapped-address errors
            raise InvalidRequestError(
                f"cannot read {length} bytes at 0x{start:08x}: {error}"
            ) from error
        return ByteWindow(
            start_address=start,
            length=read,
            data_hex=_java_bytes_to_hex(buffer)[: read * 2],
        )

    def search_constant(self, value: int, limit: int = MAX_RESULTS) -> tuple[ConstantMatch, ...]:
        self._require_open()
        validate_page(limit, 0)
        from ghidra.program.model.scalar import Scalar

        matches: list[ConstantMatch] = []
        for instruction in self._listing.getInstructions(True):
            if len(matches) >= limit:
                break
            for index in range(int(instruction.getNumOperands())):
                for operand in instruction.getOpObjects(index):
                    if not isinstance(operand, Scalar):
                        continue
                    if int(operand.getValue()) != value:
                        continue
                    containing = self._function_manager.getFunctionContaining(
                        instruction.getAddress()
                    )
                    matches.append(
                        ConstantMatch(
                            address=int(instruction.getAddress().getOffset()),
                            value=value,
                            operand_index=index,
                            mnemonic=str(instruction.getMnemonicString()),
                            function_id=(
                                None
                                if containing is None
                                else function_id_for(int(containing.getEntryPoint().getOffset()))
                            ),
                        )
                    )
        return tuple(matches)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stack.close()


class GhidraEngine(StaticAnalysisEngine):
    """Opens binaries with PyGhidra in a throwaway Ghidra project."""

    name = ENGINE_NAME

    def __init__(self, install_dir: Path | None = None) -> None:
        self._install_dir = install_dir or find_ghidra_install_dir()

    @property
    def install_dir(self) -> Path | None:
        return self._install_dir

    def is_available(self) -> bool:
        if self._install_dir is None:
            return False
        try:
            import pyghidra  # noqa: F401
        except ImportError:
            return False
        return True

    def _start_jvm(self) -> str:
        if self._install_dir is None:
            raise EngineUnavailableError(
                "no Ghidra installation found; set GHIDRA_INSTALL_DIR or install Ghidra"
            )
        try:
            import pyghidra
        except ImportError as error:
            raise EngineUnavailableError(
                "pyghidra is not installed; run `uv sync --extra ghidra`"
            ) from error
        if not pyghidra.started():
            # PyGhidra reads this variable during launch; set it so an explicitly
            # supplied install_dir wins over whatever the shell exported.
            os.environ["GHIDRA_INSTALL_DIR"] = str(self._install_dir)
            try:
                pyghidra.start(verbose=False, install_dir=self._install_dir)
            except Exception as error:  # noqa: BLE001 - launcher raises broad JVM errors
                raise EngineUnavailableError(f"could not start Ghidra: {error}") from error
        return read_ghidra_version(self._install_dir)

    def analyze_binary(
        self,
        path: str | Path,
        architecture: ArchitectureConfig | None = None,
        analyze: bool = True,
    ) -> StaticAnalysisSession:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise InvalidRequestError(f"{source} is not a file")
        requested = architecture or ArchitectureConfig()
        engine_version = self._start_jvm()
        from pyghidra.core import open_program

        stack = ExitStack()
        try:
            # A per-session project directory keeps Ghidra's writable state out
            # of the repository and guarantees runs cannot contaminate each other.
            project_dir = Path(tempfile.mkdtemp(prefix="ecu-recovery-ghidra-"))
            stack.callback(shutil.rmtree, project_dir, ignore_errors=True)
            flat = stack.enter_context(
                open_program(
                    source,
                    project_location=project_dir,
                    project_name="analysis",
                    analyze=False,
                    language=requested.language_id,
                    compiler=requested.compiler_spec_id,
                )
            )
            program = flat.getCurrentProgram()
            if requested.base_address is not None:
                self._apply_image_base(program, requested.base_address)
            if analyze:
                flat.analyzeAll(program)
            return GhidraSession(flat, stack, source, requested, engine_version)
        except AnalysisError:
            stack.close()
            raise
        except Exception as error:  # noqa: BLE001 - Ghidra import failures are Java-side
            stack.close()
            raise AnalysisError(f"Ghidra could not analyze {source.name}: {error}") from error

    @staticmethod
    def _apply_image_base(program: Any, base_address: int) -> None:
        """Relocate before analysis so discovered addresses use the real base.

        Raw ECU dumps carry no load address, so the investigator supplies one.
        """
        space = program.getAddressFactory().getDefaultAddressSpace()
        transaction = program.startTransaction("set image base")
        committed = False
        try:
            program.setImageBase(space.getAddress(base_address), True)
            committed = True
        except Exception as error:  # noqa: BLE001 - Java rejects invalid bases
            raise InvalidRequestError(
                f"could not set image base to 0x{base_address:08x}: {error}"
            ) from error
        finally:
            program.endTransaction(transaction, committed)
