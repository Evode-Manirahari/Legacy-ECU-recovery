"""End-to-end evaluation against the live engine.

Two things are proved here that no amount of unit testing can: that the
anti-leakage ordering actually holds against a real analyzer, and that the
committed baseline is reproducible rather than a snapshot nobody can re-derive.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from evaluation_support import (
    MINIMUM_FIXTURES,
    RECORDED_RESULTS,
    live_run,
    recorded_results,
    requires_ghidra,
)

from ecu_recovery.analysis.ghidra import GhidraEngine
from ecu_recovery.evaluation import groundtruth as groundtruth_module
from ecu_recovery.evaluation import harness as harness_module
from ecu_recovery.evaluation.groundtruth import DEFAULT_SAMPLES_ROOT, discover_sample_ids
from ecu_recovery.evaluation.harness import analyze_only, evaluate_fixture, freeze, frozen_session
from ecu_recovery.evaluation.models import EVIDENCE_TABLE_DATA
from ecu_recovery.evaluation.report import render_report

pytestmark = [pytest.mark.ghidra, requires_ghidra]

SAMPLE = "lookup_1d_v1"
SAMPLES_ROOT = DEFAULT_SAMPLES_ROOT


# --- the anti-leakage protocol ---


def test_analysis_completes_with_the_answer_key_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordering, proved rather than promised.

    If analysis could reach ground truth, breaking ground truth would break
    analysis. It does not.
    """

    def refuse(*args: object, **kwargs: object) -> object:
        raise AssertionError("ground truth was read during the analysis phase")

    monkeypatch.setattr(groundtruth_module, "load_ground_truth", refuse)
    monkeypatch.setattr(groundtruth_module, "read_text_symbols", refuse)
    monkeypatch.setattr(harness_module, "load_ground_truth", refuse)

    frozen = analyze_only(GhidraEngine(), SAMPLE)

    assert frozen.payload["function_count"] > 0
    assert frozen.digest


def test_the_leakage_guard_actually_bites(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without this, the test above could pass because the patch did nothing."""

    def refuse(*args: object, **kwargs: object) -> object:
        raise AssertionError("blocked")

    monkeypatch.setattr(harness_module, "load_ground_truth", refuse)

    result = evaluate_fixture(GhidraEngine(), SAMPLE)

    assert result.crashed is True
    assert result.functions is None


def test_the_frozen_result_is_unchanged_by_scoring() -> None:
    """Constant probing queries the engine; it must not move the analysis."""
    engine = GhidraEngine()
    with frozen_session(engine, SAMPLE) as (frozen, session):
        session.search_constant(20)
        session.search_constant(0)
        again = freeze(SAMPLE, session)

    assert again.digest == frozen.digest


def test_freezing_twice_gives_the_same_digest() -> None:
    engine = GhidraEngine()
    with frozen_session(engine, SAMPLE) as (frozen, session):
        assert freeze(SAMPLE, session).digest == frozen.digest


def test_analysis_reads_only_the_stripped_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run that opened firmware.symbols would be scoring its own answer key."""
    opened: list[str] = []
    original = GhidraEngine.analyze_binary

    def record(self: GhidraEngine, path: object, *args: object, **kwargs: object) -> object:
        opened.append(str(path))
        return original(self, path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(GhidraEngine, "analyze_binary", record)

    evaluate_fixture(GhidraEngine(), SAMPLE)

    assert opened
    assert all(item.endswith("firmware.stripped") for item in opened), opened


# --- the corpus run ---


def test_every_fixture_is_scored() -> None:
    run = live_run()

    assert len(run.fixtures) == len(discover_sample_ids())
    assert len(run.fixtures) >= MINIMUM_FIXTURES
    assert all(item.functions is not None for item in run.fixtures)


def test_the_static_gate_passes() -> None:
    run = live_run()

    failing = [check.metric for check in run.gate if not check.passed]
    assert failing == [], f"failing thresholds: {failing}"
    assert run.gate_passed is True


def test_no_fixture_crashed_unexpectedly() -> None:
    run = live_run()

    crashed = [(item.sample_id, item.failure) for item in run.fixtures if item.crashed]
    assert crashed == []


def test_the_live_run_reproduces_the_committed_baseline() -> None:
    """The baseline is evidence only if it can be re-derived."""
    live = json.loads(json.dumps(live_run().as_dict(), sort_keys=True))

    assert live == recorded_results(), (
        f"the live run no longer matches {RECORDED_RESULTS}; "
        "record the new baseline deliberately rather than letting it drift"
    )


def test_the_report_is_regenerated_identically() -> None:
    from evaluation_support import RECORDED_REPORT

    assert render_report(live_run()) == RECORDED_REPORT.read_text(encoding="utf-8")


def test_the_digest_does_not_depend_on_where_the_corpus_lives(tmp_path: Path) -> None:
    """The defect this guards: the baseline only reproduced in its own checkout.

    Relocating the corpus changes every absolute path and nothing about the
    program, so the frozen digest must not move.
    """
    relocated = tmp_path / "synthetic"
    shutil.copytree(SAMPLES_ROOT, relocated, symlinks=False)

    here = analyze_only(GhidraEngine(), SAMPLE)
    there = analyze_only(GhidraEngine(), SAMPLE, relocated)

    assert there.digest == here.digest
    assert there.payload["program"]["source_path"] == here.payload["program"]["source_path"]
    assert not here.payload["program"]["source_path"].startswith("/")


def test_reachable_table_data_sits_in_a_region_no_function_occupies() -> None:
    """The classification must not be quietly matching bytes in code."""
    for fixture in live_run().fixtures:
        if fixture.constants is None or fixture.functions is None:
            continue
        starts = set(fixture.functions.reported_in_scope)
        for entry in fixture.constants.entries:
            if entry.evidence != EVIDENCE_TABLE_DATA:
                continue
            assert entry.addresses
            assert entry.recovered is False
            for address in entry.addresses:
                assert not any(window.contains(address) for window in fixture.scoring_region), (
                    f"{fixture.sample_id}: {address:#x} is inside the text range"
                )
                assert address not in starts
