"""Fixture access for the static-analysis tests.

These helpers are deliberately self-contained rather than imported from the
top-level `tests/conftest.py`. `GHIDRA-001` owns `tests/analysis/**` and nothing
above it, so this directory has to stand on its own.

The opened-session cache lives here as a module global rather than in a
`tests/analysis/conftest.py`, because a second file by that name collides with
`tests/conftest.py` under strict mypy. A module global is shared by every test
module that imports it, which is exactly the sharing a session-scoped fixture
would have provided.

The ground-truth readers exist for verification only. Analysis always runs
against `firmware.stripped`; the answer key is opened afterwards, never passed
into the analyzer. See docs/synthetic-lab.md.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ecu_recovery.analysis.base import StaticAnalysisSession
from ecu_recovery.analysis.ghidra import GhidraEngine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = PROJECT_ROOT / "samples" / "synthetic"
BINARIES = SAMPLES / "binaries"
GROUND_TRUTH = SAMPLES / "ground_truth"

#: Every fixture the laboratory publishes. Read from disk rather than listed by
#: hand so a fixture added later is analyzed without editing this file.
SAMPLE_IDS = tuple(sorted(path.name for path in BINARIES.iterdir() if path.is_dir()))

#: The eight categories DATA-001 must publish. Asserted, not assumed: a
#: parametrized suite over an empty corpus passes while testing nothing.
MINIMUM_SAMPLE_COUNT = 8


def ghidra_skip_reason() -> str | None:
    """Explain why Ghidra tests cannot run, or `None` when they can."""
    try:
        import pyghidra  # noqa: F401
    except ImportError:
        return "pyghidra is not installed; run `uv sync --extra ghidra`"
    if GhidraEngine().install_dir is None:
        return "no Ghidra installation found; set GHIDRA_INSTALL_DIR"
    return None


requires_ghidra = pytest.mark.skipif(
    ghidra_skip_reason() is not None, reason=ghidra_skip_reason() or ""
)


def stripped_firmware(sample_id: str) -> Path:
    """The only artifact an investigator is allowed to see."""
    return BINARIES / sample_id / "firmware.stripped"


def ground_truth(sample_id: str) -> dict[str, Any]:
    """The hidden expectations, for scoring a finished run."""
    payload: dict[str, Any] = json.loads(
        (GROUND_TRUTH / f"{sample_id}.json").read_text(encoding="utf-8")
    )
    return payload


def ground_truth_symbols(sample_id: str) -> dict[int, str]:
    """Reveal address-to-name ground truth from the symbols-on build."""
    if shutil.which("nm") is None:
        pytest.skip("nm is required to read ground-truth symbol addresses")
    result = subprocess.run(
        ["nm", "-n", str(BINARIES / sample_id / "firmware.symbols")],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    symbols: dict[int, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        address, kind, name = parts
        if kind.lower() != "t":  # text symbols only; `A` is the Mach-O header
            continue
        symbols[int(address, 16)] = name.removeprefix("_")
    return symbols


def expected_call_edges(sample_id: str) -> set[tuple[str, str]]:
    """Ground-truth call edges as caller/callee name pairs."""
    return {
        (str(edge["caller"]), str(edge["callee"]))
        for edge in ground_truth(sample_id)["expected_call_edges"]
    }


# --- shared Ghidra sessions ---

_ENGINE: GhidraEngine | None = None
_SESSIONS: dict[str, StaticAnalysisSession] = {}


def analysis_engine() -> GhidraEngine:
    """One engine per test run. Starting the JVM twice buys nothing."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = GhidraEngine()
    return _ENGINE


def open_sample(sample_id: str) -> StaticAnalysisSession:
    """Analyze a fixture once and reuse it.

    Importing and analyzing a program costs seconds and there are eight
    fixtures, so a fresh session per test would make the suite unusable. The
    session is read-only to its callers, which is what makes sharing safe.
    """
    if sample_id not in _SESSIONS:
        _SESSIONS[sample_id] = analysis_engine().analyze_binary(stripped_firmware(sample_id))
    return _SESSIONS[sample_id]


def close_open_samples() -> None:
    """Release every cached session. Safe to call more than once."""
    while _SESSIONS:
        _, session = _SESSIONS.popitem()
        session.close()


@pytest.fixture(scope="session", autouse=True)
def close_samples_after_the_run() -> Iterator[None]:
    """Import this into any module that calls `open_sample`."""
    yield
    close_open_samples()
