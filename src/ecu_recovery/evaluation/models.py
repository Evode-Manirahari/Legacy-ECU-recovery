"""Records for one hidden-ground-truth evaluation run.

Every rate carries the counts it came from. A percentage without a numerator and
a denominator cannot be checked, argued with, or compared against a later run,
and this file is the baseline a gate decision rests on.

Nothing here imports an analysis engine. These records describe a scored run and
must stay readable on a host that cannot reproduce it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

#: Evidence classes for a declared fixture constant. Ordered strongest first.
#: `TABLE_DATA` is deliberately *not* recovery: it records that a value sits in
#: a region code takes the address of, reachable by reading bytes, while no
#: instruction operand or referenced data object carries it.
EVIDENCE_OPERAND = "operand"
EVIDENCE_REFERENCED_DATA = "referenced-data"
EVIDENCE_TABLE_DATA = "reachable-table-data"
EVIDENCE_UNSUPPORTED = "unsupported"
EVIDENCE_CLASSES = (
    EVIDENCE_OPERAND,
    EVIDENCE_REFERENCED_DATA,
    EVIDENCE_TABLE_DATA,
    EVIDENCE_UNSUPPORTED,
)

#: Only the first two are recovery under the GHIDRA-001 semantic rule.
RECOVERED_EVIDENCE = (EVIDENCE_OPERAND, EVIDENCE_REFERENCED_DATA)


def render_address(address: int) -> str:
    return f"0x{address:08x}"


@dataclass(frozen=True)
class Ratio:
    """A measurement, never a bare percentage."""

    numerator: int
    denominator: int

    @property
    def rate(self) -> float | None:
        """`None` when nothing was measured, which is not the same as zero."""
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @property
    def percent(self) -> float | None:
        rate = self.rate
        return None if rate is None else round(rate * 100, 4)

    def render(self) -> str:
        if self.denominator == 0:
            return f"n/a ({self.numerator}/{self.denominator})"
        return f"{self.percent}% ({self.numerator}/{self.denominator})"

    def as_dict(self) -> dict[str, Any]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "rate": self.rate,
            "percent": self.percent,
        }


def total(ratios: list[Ratio]) -> Ratio:
    """Micro-average: pool the counts, do not average the rates.

    Averaging per-fixture rates would give a three-function fixture the same
    weight as a six-function one, which is not what "corpus recall" means.
    """
    return Ratio(sum(item.numerator for item in ratios), sum(item.denominator for item in ratios))


@dataclass(frozen=True)
class AddressWindow:
    """An inclusive address range, named as the engine reported it."""

    name: str
    start_address: int
    end_address: int

    def contains(self, address: int) -> bool:
        return self.start_address <= address <= self.end_address

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_address": render_address(self.start_address),
            "end_address": render_address(self.end_address),
        }


@dataclass(frozen=True)
class FunctionMetrics:
    expected: tuple[int, ...]
    reported_in_scope: tuple[int, ...]
    reported_out_of_scope: tuple[int, ...]
    true_positives: tuple[int, ...]
    missed: tuple[int, ...]
    false_positives: tuple[int, ...]
    located_wrong_start: tuple[int, ...]

    @property
    def recall(self) -> Ratio:
        return Ratio(len(self.true_positives), len(self.expected))

    @property
    def precision(self) -> Ratio:
        return Ratio(len(self.true_positives), len(self.reported_in_scope))

    @property
    def start_address_accuracy(self) -> Ratio:
        """Of the expected functions the engine located at all, how many start exactly right.

        Separated from recall because "found the code but mislabelled where it
        begins" and "did not find the code" are different failures with
        different fixes.
        """
        located = len(self.true_positives) + len(self.located_wrong_start)
        return Ratio(len(self.true_positives), located)

    def as_dict(self) -> dict[str, Any]:
        return {
            "expected_count": len(self.expected),
            "reported_in_scope_count": len(self.reported_in_scope),
            "reported_out_of_scope_count": len(self.reported_out_of_scope),
            "reported_out_of_scope": [render_address(item) for item in self.reported_out_of_scope],
            "true_positives": [render_address(item) for item in self.true_positives],
            "missed": [render_address(item) for item in self.missed],
            "false_positives": [render_address(item) for item in self.false_positives],
            "located_wrong_start": [render_address(item) for item in self.located_wrong_start],
            "recall": self.recall.as_dict(),
            "precision": self.precision.as_dict(),
            "start_address_accuracy": self.start_address_accuracy.as_dict(),
        }


@dataclass(frozen=True)
class CallEdgeMetrics:
    expected: tuple[tuple[int, int], ...]
    reported_in_scope: tuple[tuple[int, int], ...]
    reported_out_of_scope: tuple[tuple[int, int], ...]
    true_positives: tuple[tuple[int, int], ...]
    missed: tuple[tuple[int, int], ...]
    false_positives: tuple[tuple[int, int], ...]

    @property
    def recall(self) -> Ratio:
        return Ratio(len(self.true_positives), len(self.expected))

    @property
    def precision(self) -> Ratio:
        return Ratio(len(self.true_positives), len(self.reported_in_scope))

    def as_dict(self) -> dict[str, Any]:
        def edges(items: tuple[tuple[int, int], ...]) -> list[list[str]]:
            return [[render_address(a), render_address(b)] for a, b in items]

        return {
            "expected_count": len(self.expected),
            "reported_in_scope_count": len(self.reported_in_scope),
            "reported_out_of_scope_count": len(self.reported_out_of_scope),
            "true_positives": edges(self.true_positives),
            "missed": edges(self.missed),
            "false_positives": edges(self.false_positives),
            "recall": self.recall.as_dict(),
            "precision": self.precision.as_dict(),
        }


@dataclass(frozen=True)
class ConstantEvidence:
    """Why one declared constant is or is not backed by analysis evidence."""

    value: int
    evidence: str
    addresses: tuple[int, ...] = ()
    detail: str = ""

    @property
    def recovered(self) -> bool:
        return self.evidence in RECOVERED_EVIDENCE

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "evidence": self.evidence,
            "recovered": self.recovered,
            "addresses": [render_address(item) for item in self.addresses],
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ConstantMetrics:
    """Reported, never gated.

    A declared constant the compiler never emitted is a property of the fixture,
    not a failure of the analyzer, so this cannot be a pass/fail threshold
    without punishing the tool for the corpus.
    """

    entries: tuple[ConstantEvidence, ...]

    def count(self, evidence: str) -> int:
        return sum(1 for item in self.entries if item.evidence == evidence)

    @property
    def recovered(self) -> Ratio:
        return Ratio(sum(1 for item in self.entries if item.recovered), len(self.entries))

    def as_dict(self) -> dict[str, Any]:
        return {
            "declared_count": len(self.entries),
            "recovered": self.recovered.as_dict(),
            "by_evidence": {name: self.count(name) for name in EVIDENCE_CLASSES},
            "entries": [item.as_dict() for item in self.entries],
        }


@dataclass(frozen=True)
class FixtureResult:
    """One fixture, analyzed then scored."""

    sample_id: str
    imported: bool
    serialized: bool
    crashed: bool
    analysis_digest: str
    scoring_region: tuple[AddressWindow, ...] = ()
    functions: FunctionMetrics | None = None
    call_edges: CallEdgeMetrics | None = None
    constants: ConstantMetrics | None = None
    analysis_warnings: tuple[tuple[str, str, int], ...] = ()
    failure: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "imported": self.imported,
            "serialized": self.serialized,
            "crashed": self.crashed,
            "failure": self.failure,
            "analysis_digest": self.analysis_digest,
            "scoring_region": [item.as_dict() for item in self.scoring_region],
            "functions": None if self.functions is None else self.functions.as_dict(),
            "call_edges": None if self.call_edges is None else self.call_edges.as_dict(),
            "constants": None if self.constants is None else self.constants.as_dict(),
            "analysis_warnings": [
                {"code": code, "severity": severity, "count": count}
                for code, severity, count in self.analysis_warnings
            ],
        }


@dataclass(frozen=True)
class GateCheck:
    metric: str
    comparison: str
    threshold: float
    observed: Ratio | None = None
    observed_count: int | None = None

    @property
    def observed_value(self) -> float | None:
        if self.observed_count is not None:
            return float(self.observed_count)
        if self.observed is None:
            return None
        return self.observed.percent

    @property
    def passed(self) -> bool:
        value = self.observed_value
        if value is None:
            # Nothing measured is not a pass. A gate that green-lights an empty
            # run is worse than no gate.
            return False
        if self.comparison == ">=":
            return value >= self.threshold
        if self.comparison == "==":
            return value == self.threshold
        raise ValueError(f"unsupported comparison {self.comparison!r}")

    def render_target(self) -> str:
        suffix = "" if self.observed_count is not None else "%"
        return f"{self.comparison} {self.threshold:g}{suffix}"

    def render_observed(self) -> str:
        if self.observed_count is not None:
            return str(self.observed_count)
        return "n/a" if self.observed is None else self.observed.render()

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "comparison": self.comparison,
            "threshold": self.threshold,
            "observed": None if self.observed is None else self.observed.as_dict(),
            "observed_count": self.observed_count,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class AggregateMetrics:
    binary_import: Ratio
    serialization: Ratio
    function_recall: Ratio
    function_precision: Ratio
    start_address_accuracy: Ratio
    call_edge_recall: Ratio
    call_edge_precision: Ratio
    unexpected_crashes: int
    constants_recovered: Ratio
    constants_by_evidence: dict[str, int] = field(default_factory=dict)
    reported_out_of_scope_functions: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "binary_import": self.binary_import.as_dict(),
            "serialization": self.serialization.as_dict(),
            "function_discovery_recall": self.function_recall.as_dict(),
            "function_discovery_precision": self.function_precision.as_dict(),
            "function_start_address_accuracy": self.start_address_accuracy.as_dict(),
            "call_edge_recall": self.call_edge_recall.as_dict(),
            "call_edge_precision": self.call_edge_precision.as_dict(),
            "unexpected_crashes": self.unexpected_crashes,
            "reported_out_of_scope_functions": self.reported_out_of_scope_functions,
            "constants_recovered": self.constants_recovered.as_dict(),
            "constants_by_evidence": dict(self.constants_by_evidence),
        }


@dataclass(frozen=True)
class ToolEnvironment:
    """What produced these numbers.

    No timestamp and no duration. The artifact is a baseline that later runs are
    diffed against, so it is byte-reproducible on a given host by construction;
    the commit that carries it is the record of when it was taken.
    """

    engine: str
    engine_version: str
    analyzer_schema_version: int
    python_version: str
    platform_system: str
    platform_machine: str
    pyghidra_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_version": self.engine_version,
            "analyzer_schema_version": self.analyzer_schema_version,
            "python_version": self.python_version,
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
            "pyghidra_version": self.pyghidra_version,
        }


@dataclass(frozen=True)
class EvaluationRun:
    environment: ToolEnvironment
    fixtures: tuple[FixtureResult, ...]
    aggregate: AggregateMetrics
    gate: tuple[GateCheck, ...]

    @property
    def gate_passed(self) -> bool:
        return all(check.passed for check in self.gate)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "environment": self.environment.as_dict(),
            "gate_passed": self.gate_passed,
            "gate": [check.as_dict() for check in self.gate],
            "aggregate": self.aggregate.as_dict(),
            "fixtures": [item.as_dict() for item in self.fixtures],
        }
