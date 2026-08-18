"""Hidden-ground-truth evaluation of the deterministic static-analysis layer.

The protocol is fixed by docs/synthetic-lab.md: analyze `firmware.stripped`,
freeze the result, and only then reveal the symbols-on addresses and the
ground-truth JSON. `harness` encodes that ordering and re-checks the frozen
digest after scoring, so the protocol is verified rather than promised.

Nothing here uses a model. Every property measured is decidable from ground
truth, and EVALS.md is explicit that software which can prove a thing must not
ask a model whether it looks right.
"""

from __future__ import annotations

from .constants import classify_constants
from .groundtruth import (
    GroundTruth,
    GroundTruthError,
    discover_sample_ids,
    load_ground_truth,
    stripped_firmware,
)
from .harness import (
    GATE_TARGETS,
    FrozenAnalysis,
    aggregate,
    analyze_only,
    check_gate,
    evaluate_fixture,
    freeze,
    frozen_session,
    run_evaluation,
)
from .models import (
    EVIDENCE_CLASSES,
    EVIDENCE_OPERAND,
    EVIDENCE_REFERENCED_DATA,
    EVIDENCE_TABLE_DATA,
    EVIDENCE_UNSUPPORTED,
    RECOVERED_EVIDENCE,
    SCHEMA_VERSION,
    AddressWindow,
    AggregateMetrics,
    CallEdgeMetrics,
    ConstantEvidence,
    ConstantMetrics,
    EvaluationRun,
    FixtureResult,
    FunctionMetrics,
    GateCheck,
    Ratio,
    ToolEnvironment,
    total,
)
from .report import render_report
from .scoring import score_call_edges, score_functions, scoring_region, warning_summary

__all__ = [
    "EVIDENCE_CLASSES",
    "EVIDENCE_OPERAND",
    "EVIDENCE_REFERENCED_DATA",
    "EVIDENCE_TABLE_DATA",
    "EVIDENCE_UNSUPPORTED",
    "GATE_TARGETS",
    "RECOVERED_EVIDENCE",
    "SCHEMA_VERSION",
    "AddressWindow",
    "AggregateMetrics",
    "CallEdgeMetrics",
    "ConstantEvidence",
    "ConstantMetrics",
    "EvaluationRun",
    "FixtureResult",
    "FrozenAnalysis",
    "FunctionMetrics",
    "GateCheck",
    "GroundTruth",
    "GroundTruthError",
    "Ratio",
    "ToolEnvironment",
    "aggregate",
    "analyze_only",
    "check_gate",
    "classify_constants",
    "discover_sample_ids",
    "evaluate_fixture",
    "freeze",
    "frozen_session",
    "load_ground_truth",
    "render_report",
    "run_evaluation",
    "score_call_edges",
    "score_functions",
    "scoring_region",
    "stripped_firmware",
    "total",
    "warning_summary",
]
