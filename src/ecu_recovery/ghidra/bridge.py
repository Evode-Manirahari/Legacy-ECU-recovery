"""Ghidra integration boundary.

Ghidra should run out of process. Its script exports JSON; this module validates
and imports that artifact. Keeping the boundary data-only avoids granting an AI
agent arbitrary host execution through the reverse-engineering tool.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import FunctionRecord


class GhidraExportError(ValueError):
    pass


def load_functions(export_path: str | Path) -> list[FunctionRecord]:
    payload = json.loads(Path(export_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("functions"), list):
        raise GhidraExportError("export must contain a functions array")
    records: list[FunctionRecord] = []
    for index, item in enumerate(payload["functions"]):
        try:
            address_value = item["address"]
            address = (
                int(address_value, 0) if isinstance(address_value, str) else int(address_value)
            )
            name = str(item["name"])
            size = None if item.get("size") is None else int(item["size"])
            decompilation = item.get("decompilation")
        except (KeyError, TypeError, ValueError) as error:
            raise GhidraExportError(f"invalid function at index {index}: {error}") from error
        if address < 0 or not name or size is not None and size < 0:
            raise GhidraExportError(f"invalid function values at index {index}")
        records.append(FunctionRecord(address, name, size, decompilation))
    return records
