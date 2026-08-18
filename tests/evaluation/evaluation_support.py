"""Shared access for the evaluation tests.

Self-contained on purpose: `EVAL-STATIC-001` owns `tests/evaluation/**` and
nothing above it. A second `conftest.py` beside `tests/conftest.py` also
collides under strict mypy, so the shared state lives in a module global that
every importing test module sees.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ecu_recovery.analysis.ghidra import GhidraEngine
from ecu_recovery.evaluation import EvaluationRun, run_evaluation

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECORDED_RESULTS = PROJECT_ROOT / "artifacts" / "evals" / "static-results.json"
RECORDED_REPORT = PROJECT_ROOT / "artifacts" / "evals" / "static-report.md"

#: The corpus DATA-001 publishes. Asserted rather than assumed, so a
#: parametrized suite cannot pass by scoring nothing.
MINIMUM_FIXTURES = 8


def ghidra_skip_reason() -> str | None:
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


def recorded_results() -> dict[str, Any]:
    """The committed baseline, read without running anything."""
    if not RECORDED_RESULTS.is_file():
        pytest.fail(f"the recorded baseline is missing at {RECORDED_RESULTS}")
    payload: dict[str, Any] = json.loads(RECORDED_RESULTS.read_text(encoding="utf-8"))
    return payload


_LIVE_RUN: EvaluationRun | None = None


def live_run() -> EvaluationRun:
    """Evaluate the whole corpus once per test session.

    A full run analyzes eight programs; repeating it per test would make the
    suite unusable for no extra signal.
    """
    global _LIVE_RUN
    if _LIVE_RUN is None:
        _LIVE_RUN = run_evaluation()
    return _LIVE_RUN
