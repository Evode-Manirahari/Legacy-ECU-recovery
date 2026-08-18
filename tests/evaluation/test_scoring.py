"""Scoring rules, checked without an engine.

The arithmetic that decides a gate has to be testable on its own. These build
analysis payloads by hand so each rule from docs/synthetic-lab.md can be pushed
at the exact case it exists for.
"""

from __future__ import annotations

from typing import Any

import pytest
from evaluation_support import MINIMUM_FIXTURES

from ecu_recovery.evaluation.groundtruth import GroundTruth
from ecu_recovery.evaluation.models import (
    EVIDENCE_CLASSES,
    EVIDENCE_OPERAND,
    EVIDENCE_TABLE_DATA,
    EVIDENCE_UNSUPPORTED,
    AggregateMetrics,
    ConstantEvidence,
    ConstantMetrics,
    GateCheck,
    Ratio,
    total,
)
from ecu_recovery.evaluation.scoring import (
    reported_call_edges,
    score_call_edges,
    score_functions,
    scoring_region,
    warning_summary,
)


def _region(name: str, start: int, end: int, executable: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "start_address": f"0x{start:08x}",
        "end_address": f"0x{end:08x}",
        "executable": executable,
        "readable": True,
        "writable": False,
        "initialized": True,
    }


def _function(start: int, end: int) -> dict[str, Any]:
    return {"start_address": f"0x{start:08x}", "end_address": f"0x{end:08x}"}


def _edge(caller: int, callee: int) -> dict[str, Any]:
    return {"caller_address": f"0x{caller:08x}", "callee_address": f"0x{callee:08x}"}


def _payload(
    functions: list[dict[str, Any]],
    edges: list[dict[str, Any]] | None = None,
    regions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "memory_regions": regions
        if regions is not None
        else [_region("__TEXT", 0x1000, 0x1FFF), _region("__text", 0x2000, 0x2FFF)],
        "functions": functions,
        "call_relationships": edges or [],
        "analysis_warnings": [],
        "program": {"endian": "little"},
    }


def _truth(
    addresses: tuple[int, ...],
    edges: tuple[tuple[int, int], ...] = (),
    constants: tuple[int, ...] = (),
) -> GroundTruth:
    return GroundTruth(
        sample_id="synthetic",
        symbols={address: f"fn_{index}" for index, address in enumerate(addresses)},
        expected_functions=tuple(f"fn_{index}" for index in range(len(addresses))),
        expected_function_addresses=addresses,
        expected_call_edges=edges,
        expected_constants=constants,
    )


# --- the scoring region ---


def test_the_scoring_region_is_where_the_fixtures_own_functions_live() -> None:
    payload = _payload([_function(0x2000, 0x20FF)])

    region = scoring_region(payload, _truth((0x2000,)))

    assert [item.name for item in region] == ["__text"]


def test_a_non_executable_region_is_never_the_scoring_region() -> None:
    payload = _payload(
        [_function(0x3000, 0x30FF)],
        regions=[_region("__const", 0x3000, 0x3FFF, executable=False)],
    )

    assert scoring_region(payload, _truth((0x3000,))) == ()


# --- function scoring ---


def test_a_true_positive_requires_the_exact_start_address() -> None:
    """One byte late is a miss, not a match. This is the whole point of the corpus."""
    payload = _payload([_function(0x2001, 0x20FF)])

    metrics = score_functions(
        payload, _truth((0x2000,)), scoring_region(payload, _truth((0x2000,)))
    )

    assert metrics.true_positives == ()
    assert metrics.missed == (0x2000,)
    assert metrics.recall == Ratio(0, 1)


def test_covering_the_entry_point_with_a_wrong_start_is_a_boundary_error() -> None:
    """Found the code, mislabelled where it begins - a different failure from not finding it."""
    payload = _payload([_function(0x1FF0, 0x20FF)])
    truth = _truth((0x2000,))

    metrics = score_functions(payload, truth, scoring_region(payload, truth))

    assert metrics.located_wrong_start == (0x2000,)
    assert metrics.start_address_accuracy == Ratio(0, 1)
    assert metrics.recall == Ratio(0, 1)


def test_startup_code_outside_the_region_is_listed_not_penalised() -> None:
    """docs/synthetic-lab.md: report compiler startup functions separately."""
    payload = _payload([_function(0x2000, 0x20FF), _function(0x1000, 0x10FF)])
    truth = _truth((0x2000,))

    metrics = score_functions(payload, truth, scoring_region(payload, truth))

    assert metrics.reported_out_of_scope == (0x1000,)
    assert metrics.false_positives == ()
    assert metrics.precision == Ratio(1, 1)


def test_an_invented_function_inside_the_region_is_a_false_positive() -> None:
    payload = _payload([_function(0x2000, 0x20FF), _function(0x2800, 0x28FF)])
    truth = _truth((0x2000,))

    metrics = score_functions(payload, truth, scoring_region(payload, truth))

    assert metrics.false_positives == (0x2800,)
    assert metrics.precision == Ratio(1, 2)
    assert metrics.recall == Ratio(1, 1)


# --- call-edge scoring ---


def test_repeated_calls_to_one_callee_count_once() -> None:
    payload = _payload([], [_edge(0x2000, 0x2100), _edge(0x2000, 0x2100)])

    assert reported_call_edges(payload) == ((0x2000, 0x2100),)


def test_call_edges_compare_exact_address_pairs() -> None:
    payload = _payload(
        [_function(0x2000, 0x20FF), _function(0x2100, 0x21FF)],
        [_edge(0x2000, 0x2100)],
    )
    truth = _truth((0x2000, 0x2100), edges=((0x2000, 0x2100),))

    metrics = score_call_edges(payload, truth, scoring_region(payload, truth))

    assert metrics.recall == Ratio(1, 1)
    assert metrics.precision == Ratio(1, 1)


def test_an_edge_reaching_outside_the_region_is_out_of_scope_not_wrong() -> None:
    payload = _payload([_function(0x2000, 0x20FF)], [_edge(0x2000, 0x1500)])
    truth = _truth((0x2000,), edges=())

    metrics = score_call_edges(payload, truth, scoring_region(payload, truth))

    assert metrics.reported_out_of_scope == ((0x2000, 0x1500),)
    assert metrics.false_positives == ()


def test_a_missed_edge_lowers_recall_not_precision() -> None:
    payload = _payload([_function(0x2000, 0x20FF), _function(0x2100, 0x21FF)], [])
    truth = _truth((0x2000, 0x2100), edges=((0x2000, 0x2100),))

    metrics = score_call_edges(payload, truth, scoring_region(payload, truth))

    assert metrics.recall == Ratio(0, 1)
    assert metrics.missed == ((0x2000, 0x2100),)
    assert metrics.precision == Ratio(0, 0)


# --- ratios and aggregation ---


def test_a_ratio_over_nothing_is_not_a_perfect_score() -> None:
    empty = Ratio(0, 0)

    assert empty.rate is None
    assert empty.percent is None
    assert "n/a" in empty.render()


def test_aggregation_pools_counts_rather_than_averaging_rates() -> None:
    """A three-function fixture must not outweigh a six-function one."""
    pooled = total([Ratio(3, 3), Ratio(3, 6)])

    assert pooled == Ratio(6, 9)
    assert pooled.percent == 66.6667


def test_every_percentage_carries_its_counts() -> None:
    rendered = Ratio(32, 32).render()

    assert rendered == "100.0% (32/32)"


# --- the gate ---


@pytest.mark.parametrize(
    "observed,threshold,expected",
    [(Ratio(95, 100), 95.0, True), (Ratio(94, 100), 95.0, False), (Ratio(100, 100), 95.0, True)],
)
def test_a_threshold_compares_against_the_observed_percentage(
    observed: Ratio, threshold: float, expected: bool
) -> None:
    check = GateCheck("function_discovery_recall", ">=", threshold, observed=observed)

    assert check.passed is expected


def test_a_gate_over_an_empty_run_fails_rather_than_passing_vacuously() -> None:
    check = GateCheck("function_discovery_recall", ">=", 95.0, observed=Ratio(0, 0))

    assert check.passed is False


def test_a_crash_count_gate_reads_the_count_not_a_percentage() -> None:
    assert GateCheck("unexpected_crashes", "==", 0.0, observed_count=0).passed is True
    assert GateCheck("unexpected_crashes", "==", 0.0, observed_count=1).passed is False


def test_an_unsupported_comparison_raises_rather_than_guessing() -> None:
    with pytest.raises(ValueError, match="unsupported comparison"):
        _ = GateCheck("x", "~=", 1.0, observed=Ratio(1, 1)).passed


# --- constants ---


def test_only_operand_and_referenced_data_count_as_recovery() -> None:
    """Reachable bytes are reported, and deliberately do not count."""
    metrics = ConstantMetrics(
        entries=(
            ConstantEvidence(1, EVIDENCE_OPERAND),
            ConstantEvidence(2, EVIDENCE_TABLE_DATA, (0x3000,)),
            ConstantEvidence(0, EVIDENCE_UNSUPPORTED),
        )
    )

    assert metrics.recovered == Ratio(1, 3)
    assert metrics.count(EVIDENCE_TABLE_DATA) == 1


def test_constants_are_never_part_of_the_gate() -> None:
    """A constant the compiler removed is a fixture property, not a tool failure."""
    from ecu_recovery.evaluation.harness import GATE_TARGETS

    assert not [metric for metric, _, _ in GATE_TARGETS if "constant" in metric]


def test_the_evidence_classes_are_exactly_the_four_reported() -> None:
    assert EVIDENCE_CLASSES == (
        "operand",
        "referenced-data",
        "reachable-table-data",
        "unsupported",
    )


# --- misc ---


def test_warnings_collapse_to_code_severity_counts() -> None:
    payload = _payload([])
    payload["analysis_warnings"] = [
        {"code": "a", "severity": "info", "address": None},
        {"code": "a", "severity": "info", "address": "0x1"},
        {"code": "b", "severity": "error", "address": None},
    ]

    assert warning_summary(payload) == (("a", "info", 2), ("b", "error", 1))


def test_the_aggregate_reports_out_of_scope_functions_separately() -> None:
    metrics = AggregateMetrics(
        binary_import=Ratio(1, 1),
        serialization=Ratio(1, 1),
        function_recall=Ratio(1, 1),
        function_precision=Ratio(1, 1),
        start_address_accuracy=Ratio(1, 1),
        call_edge_recall=Ratio(1, 1),
        call_edge_precision=Ratio(1, 1),
        unexpected_crashes=0,
        constants_recovered=Ratio(1, 1),
        reported_out_of_scope_functions=4,
    )

    assert metrics.as_dict()["reported_out_of_scope_functions"] == 4


def test_the_corpus_expectation_is_stated_not_assumed() -> None:
    assert MINIMUM_FIXTURES == 8
