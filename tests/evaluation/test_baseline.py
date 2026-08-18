"""Regression over the recorded baseline.

EVALS.md requires a baseline that is never silently replaced, which is why
`artifacts/evals/` is committed. These tests read that file and recompute it:
every percentage from its own counts, every aggregate from the per-fixture
counts, and every gate verdict from the aggregate.

None of this needs Ghidra, so CI checks the committed numbers on every push even
though it cannot reproduce them. A baseline nobody can re-derive is a claim, not
evidence.
"""

from __future__ import annotations

from typing import Any

import pytest
from evaluation_support import MINIMUM_FIXTURES, RECORDED_REPORT, recorded_results

from ecu_recovery.evaluation.harness import GATE_TARGETS, check_gate
from ecu_recovery.evaluation.models import (
    EVIDENCE_CLASSES,
    RECOVERED_EVIDENCE,
    SCHEMA_VERSION,
    AggregateMetrics,
    Ratio,
)

RATIO_KEYS = ("numerator", "denominator", "rate", "percent")


def _ratios(payload: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
    """Every ratio anywhere in the document, with the path that reached it."""
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(payload, dict):
        if all(key in payload for key in RATIO_KEYS):
            found.append((path, payload))
        for key, value in payload.items():
            found.extend(_ratios(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_ratios(value, f"{path}[{index}]"))
    return found


def test_the_baseline_exists_and_declares_its_schema() -> None:
    payload = recorded_results()

    assert payload["schema_version"] == SCHEMA_VERSION
    assert RECORDED_REPORT.is_file(), "the Markdown report must be committed beside the JSON"


def test_the_whole_corpus_was_scored() -> None:
    fixtures = recorded_results()["fixtures"]

    assert len(fixtures) >= MINIMUM_FIXTURES
    assert len({item["sample_id"] for item in fixtures}) == len(fixtures)


def test_every_percentage_is_recomputable_from_its_own_counts() -> None:
    for path, ratio in _ratios(recorded_results()):
        rebuilt = Ratio(ratio["numerator"], ratio["denominator"])
        assert rebuilt.percent == ratio["percent"], path
        assert rebuilt.rate == ratio["rate"], path


def test_no_denominator_is_smaller_than_its_numerator() -> None:
    for path, ratio in _ratios(recorded_results()):
        assert ratio["numerator"] <= ratio["denominator"], path


def test_the_aggregate_is_the_sum_of_the_per_fixture_counts() -> None:
    """Catches an aggregate edited by hand, or averaged instead of pooled."""
    payload = recorded_results()
    fixtures = payload["fixtures"]
    aggregate = payload["aggregate"]

    for aggregate_key, section, metric in (
        ("function_discovery_recall", "functions", "recall"),
        ("function_discovery_precision", "functions", "precision"),
        ("function_start_address_accuracy", "functions", "start_address_accuracy"),
        ("call_edge_recall", "call_edges", "recall"),
        ("call_edge_precision", "call_edges", "precision"),
    ):
        scored = [item[section][metric] for item in fixtures if item[section] is not None]
        assert aggregate[aggregate_key]["numerator"] == sum(item["numerator"] for item in scored)
        assert aggregate[aggregate_key]["denominator"] == sum(
            item["denominator"] for item in scored
        )

    assert aggregate["binary_import"] == {
        **aggregate["binary_import"],
        "numerator": sum(1 for item in fixtures if item["imported"]),
        "denominator": len(fixtures),
    }
    assert aggregate["unexpected_crashes"] == sum(1 for item in fixtures if item["crashed"])


def test_the_gate_verdicts_follow_from_the_recorded_aggregate() -> None:
    payload = recorded_results()
    aggregate = payload["aggregate"]

    def ratio(key: str) -> Ratio:
        return Ratio(aggregate[key]["numerator"], aggregate[key]["denominator"])

    rebuilt = check_gate(
        AggregateMetrics(
            binary_import=ratio("binary_import"),
            serialization=ratio("serialization"),
            function_recall=ratio("function_discovery_recall"),
            function_precision=ratio("function_discovery_precision"),
            start_address_accuracy=ratio("function_start_address_accuracy"),
            call_edge_recall=ratio("call_edge_recall"),
            call_edge_precision=ratio("call_edge_precision"),
            unexpected_crashes=aggregate["unexpected_crashes"],
            constants_recovered=ratio("constants_recovered"),
        )
    )

    recorded = {item["metric"]: item["passed"] for item in payload["gate"]}
    assert {check.metric: check.passed for check in rebuilt} == recorded
    assert payload["gate_passed"] == all(recorded.values())


def test_the_recorded_gate_covers_every_required_threshold() -> None:
    recorded = {
        item["metric"]: (item["comparison"], item["threshold"])
        for item in recorded_results()["gate"]
    }

    assert recorded == {
        metric: (comparison, threshold) for metric, comparison, threshold in GATE_TARGETS
    }


@pytest.mark.parametrize(
    "metric,comparison,threshold",
    [
        ("binary_import", "==", 100.0),
        ("serialization", "==", 100.0),
        ("function_discovery_recall", ">=", 95.0),
        ("function_discovery_precision", ">=", 95.0),
        ("call_edge_recall", ">=", 90.0),
        ("unexpected_crashes", "==", 0.0),
    ],
)
def test_the_thresholds_are_the_ones_the_contract_states(
    metric: str, comparison: str, threshold: float
) -> None:
    """A silently lowered gate is the failure EVALS.md names explicitly."""
    recorded = {item["metric"]: item for item in recorded_results()["gate"]}

    assert recorded[metric]["comparison"] == comparison
    assert recorded[metric]["threshold"] == threshold


def test_constant_recovery_counts_only_the_two_evidence_classes_that_qualify() -> None:
    for fixture in recorded_results()["fixtures"]:
        constants = fixture["constants"]
        if constants is None:
            continue
        by_evidence = constants["by_evidence"]
        assert sum(by_evidence.values()) == constants["declared_count"], fixture["sample_id"]
        assert constants["recovered"]["numerator"] == sum(
            by_evidence[name] for name in RECOVERED_EVIDENCE
        ), fixture["sample_id"]
        assert set(by_evidence) == set(EVIDENCE_CLASSES)


def test_reachable_table_data_is_recorded_but_never_counted_as_recovered() -> None:
    """The rule that keeps matching bytes out of the score."""
    for fixture in recorded_results()["fixtures"]:
        constants = fixture["constants"]
        if constants is None:
            continue
        for entry in constants["entries"]:
            if entry["evidence"] in ("reachable-table-data", "unsupported"):
                assert entry["recovered"] is False, (fixture["sample_id"], entry["value"])


def test_every_scored_fixture_imported_serialized_and_did_not_crash() -> None:
    for fixture in recorded_results()["fixtures"]:
        if fixture["functions"] is None:
            continue
        assert fixture["imported"] is True
        assert fixture["serialized"] is True
        assert fixture["crashed"] is False
        assert fixture["analysis_digest"], "a scored fixture must record what was frozen"


def test_the_baseline_carries_no_timestamp_so_it_stays_reproducible() -> None:
    """A wall clock in the artifact would make every rerun a spurious diff."""
    text = str(recorded_results())

    for token in ("timestamp", "generated_at", "duration", "elapsed"):
        assert token not in text.lower()


def test_the_environment_that_produced_the_baseline_is_recorded() -> None:
    environment = recorded_results()["environment"]

    assert environment["engine"] == "ghidra"
    assert environment["engine_version"] not in ("", "unknown", "unavailable")
    assert environment["pyghidra_version"] != "not installed"
    assert environment["platform_machine"]
