"""Deterministic evaluation of the investigator agent.

The shape is fixed by the same argument that ordered the static phase:

    frozen transcript + hidden ground truth -> deterministic metrics

Freezing the transcript is what separates the two questions. Re-running the
scorer over a fixed transcript measures the scorer; re-running the agent
produces a new transcript and measures the agent. Entangled, a change in either
looks like a change in both.

Scoring touches no model and no network. It reads JSON.

This package does not modify `AGENT-001`. A node that repairs what it grades has
stopped being a measurement.
"""

from __future__ import annotations

from .adjudication import (
    REQUIRED_HUMAN_REVIEWERS,
    AdjudicationError,
    ClaimJudgement,
    Review,
    ReviewPanel,
    Verdict,
    load_panel,
    parse_review,
)
from .gate import GATE_TARGETS, AgentGateCheck, check_gate
from .models import (
    FACTUAL_SUPPORT,
    SCHEMA_VERSION,
    AgentEvaluationRun,
    AgentMetrics,
    CalibrationBucket,
    ClassificationScore,
    ConfidenceBucket,
    Measurement,
    Provenance,
    TranscriptScore,
)
from .report import render_report
from .runner import evaluate
from .scoring import (
    aggregate,
    calibration_buckets,
    classification_accuracy,
    confidence_buckets,
    confidence_calibration,
    critical_unsupported_claims,
    expected_roles,
    score_classification,
    score_transcript,
)
from .transcripts import (
    TRANSCRIPT_SCHEMA_VERSION,
    Transcript,
    TranscriptError,
    load_transcripts,
    parse_transcript,
)

__all__ = [
    "parse_review",
    "load_panel",
    "critical_unsupported_claims",
    "confidence_calibration",
    "classification_accuracy",
    "calibration_buckets",
    "Verdict",
    "ReviewPanel",
    "Review",
    "Measurement",
    "ClaimJudgement",
    "CalibrationBucket",
    "AdjudicationError",
    "REQUIRED_HUMAN_REVIEWERS",
    "FACTUAL_SUPPORT",
    "GATE_TARGETS",
    "SCHEMA_VERSION",
    "TRANSCRIPT_SCHEMA_VERSION",
    "AgentEvaluationRun",
    "AgentGateCheck",
    "AgentMetrics",
    "ClassificationScore",
    "ConfidenceBucket",
    "Provenance",
    "Transcript",
    "TranscriptError",
    "TranscriptScore",
    "aggregate",
    "check_gate",
    "confidence_buckets",
    "expected_roles",
    "load_transcripts",
    "parse_transcript",
    "render_report",
    "score_classification",
    "score_transcript",
    "evaluate",
]
