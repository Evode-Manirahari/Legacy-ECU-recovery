"""Helpers for evidence-model tests.

Named `evidence_support` for the reason `tests/graph/support.py` records:
pytest puts every test directory on `sys.path`, so a `conftest` here would
shadow `tests/conftest`, and a bare `support` would collide with the graph
tests' own helper module. A unique name avoids both.

Everything the evidence model does is deterministic, so these helpers need no
sample binary and no analysis engine.
"""

from __future__ import annotations

from pathlib import Path

from ecu_recovery.intake import profile_binary
from ecu_recovery.store import InvestigationStore


def investigation(tmp_path: Path) -> tuple[InvestigationStore, int]:
    """A fresh store holding one profiled binary, and that binary's id."""
    firmware = tmp_path / "fixture.rom"
    firmware.write_bytes(bytes(range(256)))
    store = InvestigationStore(tmp_path / "analysis.sqlite3")
    return store, store.save_profile(profile_binary(firmware))
