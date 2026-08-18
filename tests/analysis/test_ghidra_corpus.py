"""Deterministic extraction across the whole synthetic corpus.

Every fixture is analyzed, not just the two the pre-graph tests used. A static
analyzer that works on one sample and not the next is not a tool yet.

Analysis always runs against `firmware.stripped`. Ground truth is opened after
the session exists, which is the evaluation boundary docs/synthetic-lab.md sets.
GHIDRA-001 asserts that extraction recovers the structure; scoring it is
EVAL-STATIC-001's job, not this file's.
"""

from __future__ import annotations

import json

import pytest
from analysis_support import (
    SAMPLE_IDS,
    analysis_engine,
    close_samples_after_the_run,  # noqa: F401 - session teardown, used by pytest
    expected_call_edges,
    ground_truth,
    ground_truth_symbols,
    open_sample,
    requires_ghidra,
    stripped_firmware,
)

from ecu_recovery.analysis.base import WARNING_AUTO_ANALYSIS_SKIPPED

pytestmark = [pytest.mark.ghidra, requires_ghidra]


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_discovers_exactly_the_ground_truth_functions(sample_id: str) -> None:
    session = open_sample(sample_id)

    discovered = {function.start_address for function in session.export().functions}

    expected = set(ground_truth_symbols(sample_id))
    assert discovered == expected, (
        f"missed {sorted(expected - discovered)}, invented {sorted(discovered - expected)}"
    )


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_recovers_exactly_the_ground_truth_call_graph(sample_id: str) -> None:
    session = open_sample(sample_id)
    edges = session.export().call_relationships

    symbols = ground_truth_symbols(sample_id)
    named = {(symbols[edge.caller_address], symbols[edge.callee_address]) for edge in edges}

    assert named == expected_call_edges(sample_id)


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_the_export_carries_every_required_category_and_holds_no_java(sample_id: str) -> None:
    analysis = open_sample(sample_id).export()

    # A leaked Java object fails json.dumps, so this is the boundary check.
    payload = json.loads(json.dumps(analysis.as_dict()))

    assert payload["program"]["language_id"] == "x86:LE:64:default"
    assert payload["program"]["processor"] == "x86"
    assert payload["program"]["endian"] == "little"
    assert payload["memory_regions"]
    assert payload["function_count"] == len(ground_truth_symbols(sample_id))
    assert payload["functions"]
    assert payload["call_relationships"]
    assert isinstance(payload["analysis_warnings"], list)


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_expected_functions_are_all_named_in_the_ground_truth_symbols(sample_id: str) -> None:
    """Guards the mapping the previous two tests depend on.

    If `nm` and the ground-truth file ever disagree, the comparisons above would
    silently compare the wrong things.
    """
    open_sample(sample_id)

    names = set(ground_truth_symbols(sample_id).values())

    assert names == set(ground_truth(sample_id)["expected_functions"])


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_function_bodies_stay_inside_a_mapped_executable_region(sample_id: str) -> None:
    session = open_sample(sample_id)
    analysis = session.export()

    executable = [region for region in analysis.memory_regions if region.executable]

    for function in analysis.functions:
        assert any(
            region.contains(function.start_address) and region.contains(function.end_address)
            for region in executable
        ), f"{function.id} falls outside every executable region"


def test_two_independent_runs_produce_an_identical_export() -> None:
    """Determinism is the whole claim of this node; measure it directly."""
    firmware = stripped_firmware(SAMPLE_IDS[0])
    engine = analysis_engine()

    with engine.analyze_binary(firmware) as first:
        one = json.dumps(first.export().as_dict(), sort_keys=True)
    with engine.analyze_binary(firmware) as second:
        two = json.dumps(second.export().as_dict(), sort_keys=True)

    assert one == two


def test_skipping_auto_analysis_is_reported_rather_than_silently_shrinking_results() -> None:
    firmware = stripped_firmware(SAMPLE_IDS[0])
    with analysis_engine().analyze_binary(firmware, analyze=False) as session:
        analysis = session.export()

    codes = {item.code for item in analysis.analysis_warnings}
    assert WARNING_AUTO_ANALYSIS_SKIPPED in codes
    assert analysis.program.auto_analysis_ran is False
    # The point of the warning: this run finds almost nothing, and a reader must
    # not mistake that for a firmware image that contains almost nothing.
    assert len(analysis.functions) < len(ground_truth_symbols(SAMPLE_IDS[0]))
