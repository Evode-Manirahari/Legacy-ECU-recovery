"""Scoring rules from docs/synthetic-lab.md, applied to a frozen analysis.

Every function here reads the *serialized* analysis payload rather than a live
session. That is deliberate: what gets scored is then provably the same bytes
that were frozen before the answer key was opened, and the scoring logic stays
testable without a JVM.

Comparison is by exact address throughout. An approximate match would let a
disassembler that puts a function boundary one instruction early score as
correct, which is the exact failure this corpus exists to catch.
"""

from __future__ import annotations

from typing import Any

from .groundtruth import GroundTruth
from .models import AddressWindow, CallEdgeMetrics, FunctionMetrics


def parse_address(value: str | int) -> int:
    return value if isinstance(value, int) else int(value, 16)


def memory_windows(payload: dict[str, Any]) -> tuple[AddressWindow, ...]:
    return tuple(
        AddressWindow(
            name=str(region["name"]),
            start_address=parse_address(region["start_address"]),
            end_address=parse_address(region["end_address"]),
        )
        for region in payload["memory_regions"]
    )


def scoring_region(payload: dict[str, Any], truth: GroundTruth) -> tuple[AddressWindow, ...]:
    """The fixture's own text range.

    Defined as the executable regions that hold at least one ground-truth
    function, rather than by hard-coding a section name, so the rule survives a
    change of object format. Everything the engine reports outside it is
    compiler or runtime startup code: real output, but not this fixture's, and
    docs/synthetic-lab.md requires it be listed separately instead of counted
    as a false positive.
    """
    executable = [
        window
        for window, region in zip(memory_windows(payload), payload["memory_regions"], strict=True)
        if bool(region["executable"])
    ]
    return tuple(
        window
        for window in executable
        if any(window.contains(address) for address in truth.expected_function_addresses)
    )


def in_region(address: int, region: tuple[AddressWindow, ...]) -> bool:
    return any(window.contains(address) for window in region)


def reported_function_bodies(payload: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    return tuple(
        (parse_address(item["start_address"]), parse_address(item["end_address"]))
        for item in payload["functions"]
    )


def score_functions(
    payload: dict[str, Any], truth: GroundTruth, region: tuple[AddressWindow, ...]
) -> FunctionMetrics:
    bodies = reported_function_bodies(payload)
    starts_in_scope = sorted({start for start, _ in bodies if in_region(start, region)})
    starts_out_of_scope = sorted({start for start, _ in bodies if not in_region(start, region)})
    expected = tuple(sorted(truth.expected_function_addresses))
    expected_set = set(expected)

    true_positives = tuple(address for address in expected if address in set(starts_in_scope))
    # "Located" means some reported body covers the real entry point. Splitting
    # this out separates a boundary error from a discovery failure.
    located_wrong_start = tuple(
        address
        for address in expected
        if address not in set(starts_in_scope)
        and any(start <= address <= end for start, end in bodies)
    )
    missed = tuple(address for address in expected if address not in set(true_positives))
    false_positives = tuple(address for address in starts_in_scope if address not in expected_set)
    return FunctionMetrics(
        expected=expected,
        reported_in_scope=tuple(starts_in_scope),
        reported_out_of_scope=tuple(starts_out_of_scope),
        true_positives=true_positives,
        missed=missed,
        false_positives=false_positives,
        located_wrong_start=located_wrong_start,
    )


def reported_call_edges(payload: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    """Deduplicated caller/callee address pairs.

    The analyzer already collapses repeated call sites to one edge; this keeps
    the guarantee local so scoring does not silently depend on it.
    """
    return tuple(
        sorted(
            {
                (parse_address(edge["caller_address"]), parse_address(edge["callee_address"]))
                for edge in payload["call_relationships"]
            }
        )
    )


def score_call_edges(
    payload: dict[str, Any], truth: GroundTruth, region: tuple[AddressWindow, ...]
) -> CallEdgeMetrics:
    reported = reported_call_edges(payload)
    in_scope = tuple(
        edge for edge in reported if in_region(edge[0], region) and in_region(edge[1], region)
    )
    out_of_scope = tuple(edge for edge in reported if edge not in set(in_scope))
    expected = tuple(sorted(set(truth.expected_call_edges)))

    true_positives = tuple(edge for edge in expected if edge in set(in_scope))
    missed = tuple(edge for edge in expected if edge not in set(in_scope))
    false_positives = tuple(edge for edge in in_scope if edge not in set(expected))
    return CallEdgeMetrics(
        expected=expected,
        reported_in_scope=in_scope,
        reported_out_of_scope=out_of_scope,
        true_positives=true_positives,
        missed=missed,
        false_positives=false_positives,
    )


def warning_summary(payload: dict[str, Any]) -> tuple[tuple[str, str, int], ...]:
    """Collapse the analysis warnings to (code, severity, count)."""
    counts: dict[tuple[str, str], int] = {}
    for warning in payload.get("analysis_warnings", ()):
        key = (str(warning["code"]), str(warning["severity"]))
        counts[key] = counts.get(key, 0) + 1
    return tuple((code, severity, count) for (code, severity), count in sorted(counts.items()))
