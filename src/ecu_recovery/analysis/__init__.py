"""Deterministic analysis boundaries.

Prompt 1 intentionally provides only the package boundary. PyGhidra analysis is
reserved for Prompt 3.
"""

from ..ghidra.bridge import GhidraExportError, load_functions
from ..models import FunctionRecord

__all__ = ["FunctionRecord", "GhidraExportError", "load_functions"]
