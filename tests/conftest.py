"""Shared fixtures for Ghidra-backed tests.

Starting the Ghidra JVM costs far more than any single assertion, so the engine
is session scoped. Sessions themselves are module scoped per sample because a
`GhidraSession` is not safe to share across threads and holds a project open.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from ecu_recovery.analysis.ghidra import GhidraEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = PROJECT_ROOT / "samples" / "synthetic" / "binaries"


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
    return SAMPLES / sample_id / "firmware.stripped"


def ground_truth_symbols(sample_id: str) -> dict[int, str]:
    """Reveal address-to-name ground truth from the symbols-on build.

    Only call this after an analysis run is complete. The stripped build is what
    gets analyzed; this is the answer key, read afterwards for scoring.
    """
    if shutil.which("nm") is None:
        pytest.skip("nm is required to read ground-truth symbol addresses")
    result = subprocess.run(
        ["nm", "-n", str(SAMPLES / sample_id / "firmware.symbols")],
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


@pytest.fixture(scope="session")
def engine() -> GhidraEngine:
    return GhidraEngine()
