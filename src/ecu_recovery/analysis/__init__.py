"""Deterministic static-analysis boundary.

Import analysis types from here rather than from an engine module. `models` and
`base` are engine-free; only `ghidra` knows Ghidra exists, and it is imported
lazily so this package stays importable on a host without Ghidra installed.

`ecu_recovery.models.FunctionRecord` remains the storage record used by the
SQLite store and the report. `analysis.models.FunctionRecord` is the richer
analysis record. `to_storage_record` converts between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..ghidra.bridge import GhidraExportError, load_functions
from ..models import FunctionRecord as StoredFunctionRecord
from .base import (
    DEFAULT_PAGE_SIZE,
    MAX_INSTRUCTIONS,
    MAX_READ_BYTES,
    MAX_RESULTS,
    AnalysisError,
    EngineUnavailableError,
    InvalidRequestError,
    StaticAnalysisEngine,
    StaticAnalysisSession,
    UnknownFunctionError,
)
from .models import (
    AnalysisExport,
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
    render_address,
)

if TYPE_CHECKING:
    from .ghidra import GhidraEngine


def to_storage_record(
    function: FunctionRecord, decompilation: str | None = None
) -> StoredFunctionRecord:
    """Narrow an analysis record to the record the SQLite store persists."""
    return StoredFunctionRecord(
        address=function.start_address,
        name=function.name,
        size=function.size,
        decompilation=decompilation,
    )


def __getattr__(name: str) -> Any:
    """Expose `GhidraEngine` without importing the engine at package import."""
    if name == "GhidraEngine":
        from .ghidra import GhidraEngine as engine

        return engine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_INSTRUCTIONS",
    "MAX_READ_BYTES",
    "MAX_RESULTS",
    "AnalysisError",
    "AnalysisExport",
    "ArchitectureConfig",
    "ByteWindow",
    "ConstantMatch",
    "CrossReference",
    "DecompilerResult",
    "DisassemblyResult",
    "EngineUnavailableError",
    "FunctionRecord",
    "GhidraEngine",
    "GhidraExportError",
    "Instruction",
    "InvalidRequestError",
    "MemoryRegion",
    "ProgramSummary",
    "StaticAnalysisEngine",
    "StaticAnalysisSession",
    "StoredFunctionRecord",
    "StringRecord",
    "UnknownFunctionError",
    "function_id_for",
    "load_functions",
    "render_address",
    "to_storage_record",
]
