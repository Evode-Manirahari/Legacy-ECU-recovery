"""Deterministic static-analysis boundary.

Import analysis types from here rather than from an engine module. `models` and
`base` are engine-free; only `ghidra` knows Ghidra exists, and it is imported
lazily so this package stays importable on a host without Ghidra installed.

`ecu_recovery.models.FunctionRecord` remains the storage record used by the
SQLite store and the report. `analysis.models.FunctionRecord` is the richer
analysis record. `to_storage_record` converts between them.

`BinaryAnalysis` is the complete result of one run. `AnalysisExport` is the
name it shipped under before the node contract fixed the required model names,
and remains an alias of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..ghidra.bridge import GhidraExportError, load_functions
from ..models import FunctionRecord as StoredFunctionRecord
from .base import (
    DEFAULT_PAGE_SIZE,
    MAX_EXPORT_FUNCTIONS,
    MAX_EXPORT_STRINGS,
    MAX_INSTRUCTIONS,
    MAX_READ_BYTES,
    MAX_RESULTS,
    WARNING_AUTO_ANALYSIS_SKIPPED,
    WARNING_COMPILER_SPEC_DECLARED,
    WARNING_DECOMPILATION_FAILED,
    WARNING_ENGINE_DIAGNOSTIC,
    WARNING_FUNCTIONS_TRUNCATED,
    WARNING_IMAGE_BASE_OVERRIDDEN,
    WARNING_LANGUAGE_DECLARED,
    WARNING_NO_FUNCTIONS,
    WARNING_STRINGS_TRUNCATED,
    WARNING_UNCOVERED_CODE_BYTES,
    WARNING_UNINITIALIZED_BLOCK,
    AnalysisError,
    EngineUnavailableError,
    InvalidRequestError,
    StaticAnalysisEngine,
    StaticAnalysisSession,
    UnknownFunctionError,
)
from .models import (
    CONSTANT_KIND_DATA,
    CONSTANT_KIND_OPERAND,
    WARNING_SEVERITIES,
    AnalysisExport,
    AnalysisWarning,
    ArchitectureConfig,
    BinaryAnalysis,
    ByteWindow,
    CallEdge,
    ConstantMatch,
    CrossReference,
    DecompilerResult,
    DisassemblyResult,
    FunctionRecord,
    Instruction,
    MemoryRegion,
    ProgramSummary,
    StringRecord,
    address_of_function_id,
    call_edges_from,
    function_id_for,
    render_address,
    sorted_warnings,
)
from .render import render_analysis_summary

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
    "CONSTANT_KIND_DATA",
    "CONSTANT_KIND_OPERAND",
    "DEFAULT_PAGE_SIZE",
    "MAX_EXPORT_FUNCTIONS",
    "MAX_EXPORT_STRINGS",
    "MAX_INSTRUCTIONS",
    "MAX_READ_BYTES",
    "MAX_RESULTS",
    "WARNING_AUTO_ANALYSIS_SKIPPED",
    "WARNING_COMPILER_SPEC_DECLARED",
    "WARNING_DECOMPILATION_FAILED",
    "WARNING_ENGINE_DIAGNOSTIC",
    "WARNING_FUNCTIONS_TRUNCATED",
    "WARNING_IMAGE_BASE_OVERRIDDEN",
    "WARNING_LANGUAGE_DECLARED",
    "WARNING_NO_FUNCTIONS",
    "WARNING_SEVERITIES",
    "WARNING_STRINGS_TRUNCATED",
    "WARNING_UNCOVERED_CODE_BYTES",
    "WARNING_UNINITIALIZED_BLOCK",
    "AnalysisError",
    "AnalysisExport",
    "AnalysisWarning",
    "ArchitectureConfig",
    "BinaryAnalysis",
    "ByteWindow",
    "CallEdge",
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
    "address_of_function_id",
    "call_edges_from",
    "function_id_for",
    "load_functions",
    "render_address",
    "render_analysis_summary",
    "sorted_warnings",
    "to_storage_record",
]
