"""Records for one agent evaluation run.

`Ratio` and the gate machinery are reused from the static evaluator rather than
reinvented: a second way to express "27 of 41" would eventually disagree with
the first, and the argument for publishing counts beside every rate is identical
here.

What is new is the subject. `EVAL-STATIC-001` scored facts a tool derived;
this scores claims a model made about them. The difference shows up in one
place worth naming: several of these metrics are gated at a perfect score, not
because perfection is expected of a model, but because they measure the
*machinery around* it. A fabricated citation reaching a surviving claim is not
the model being wrong, it is the checking having failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import Ratio, total

SCHEMA_VERSION = 1

#: A claim asserting something about the program, as opposed to admitting it
#: cannot tell. Only these carry an evidential burden.
FACTUAL_SUPPORT = ("observed", "inferred")


@dataclass(frozen=True)
class ClassificationScore:
    """A lexical proxy for whether a claim describes the right role.

    Deliberately crude, and published as a baseline rather than a gate. EVALS.md
    reserves semantic classification for two blinded human reviewers, and a term
    overlap is not that. It is reported because an unmeasured number invites
    someone to assume it, and because a proxy whose definition is stated can at
    least be argued with.
    """

    subject: str
    expected_role: str
    matched_terms: tuple[str, ...]
    missed_terms: tuple[str, ...]

    @property
    def recall(self) -> Ratio:
        return Ratio(len(self.matched_terms), len(self.matched_terms) + len(self.missed_terms))

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "expected_role": self.expected_role,
            "matched_terms": list(self.matched_terms),
            "missed_terms": list(self.missed_terms),
            "term_recall": self.recall.as_dict(),
        }


@dataclass(frozen=True)
class ConfidenceBucket:
    lower: float
    upper: float
    claims: int
    supported: int

    @property
    def observed(self) -> Ratio:
        return Ratio(self.supported, self.claims)

    @property
    def midpoint(self) -> float:
        return round((self.lower + self.upper) / 2, 4)

    @property
    def gap(self) -> float | None:
        """Stated confidence minus observed support. Positive means overconfident."""
        rate = self.observed.rate
        return None if rate is None else round(self.midpoint - rate, 4)

    def as_dict(self) -> dict[str, Any]:
        return {
            "range": [self.lower, self.upper],
            "midpoint": self.midpoint,
            "claims": self.claims,
            "supported": self.supported,
            "observed_support": self.observed.as_dict(),
            "calibration_gap": self.gap,
        }


@dataclass(frozen=True)
class TranscriptScore:
    """One frozen transcript, scored."""

    transcript_id: str
    sample_id: str
    subject: str
    scenario: str
    parsed: bool
    claims: int
    factual_claims: int
    citations: int
    valid_citations: int
    fabricated_citations: int
    unsupported_factual_claims: int
    critical_unsupported_claims: int
    demotions: int
    classification: ClassificationScore | None = None
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "transcript_id": self.transcript_id,
            "sample_id": self.sample_id,
            "subject": self.subject,
            "scenario": self.scenario,
            "parsed": self.parsed,
            "claims": self.claims,
            "factual_claims": self.factual_claims,
            "citations": self.citations,
            "valid_citations": self.valid_citations,
            "fabricated_citations": self.fabricated_citations,
            "unsupported_factual_claims": self.unsupported_factual_claims,
            "critical_unsupported_claims": self.critical_unsupported_claims,
            "demotions": self.demotions,
            "classification": None
            if self.classification is None
            else self.classification.as_dict(),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class AgentMetrics:
    evidence_reference_validity: Ratio
    schema_compliance: Ratio
    unsupported_factual_claims: Ratio
    tool_hallucinations: int
    critical_unsupported_claims: int
    classification_term_recall: Ratio
    confidence_buckets: tuple[ConfidenceBucket, ...] = ()
    transcripts: int = 0
    demotions: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "transcripts": self.transcripts,
            "evidence_reference_validity": self.evidence_reference_validity.as_dict(),
            "schema_compliance": self.schema_compliance.as_dict(),
            "unsupported_factual_claims": self.unsupported_factual_claims.as_dict(),
            "tool_hallucinations": self.tool_hallucinations,
            "critical_unsupported_claims": self.critical_unsupported_claims,
            "demotions": self.demotions,
            "classification_term_recall_baseline": self.classification_term_recall.as_dict(),
            "confidence_calibration": [item.as_dict() for item in self.confidence_buckets],
        }


@dataclass(frozen=True)
class Provenance:
    """Where the transcripts came from, stated so a number cannot be over-read.

    `authored` means a scripted reply stood in for a model. It verifies the
    scoring machinery and is not a baseline of any model's behaviour, and the
    gate must not be declared passed on that basis.
    """

    kind: str = "authored"
    detail: str = "scripted replies over real tool output; no model was called"

    @property
    def is_real_model(self) -> bool:
        return self.kind == "model"

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail, "is_real_model": self.is_real_model}


@dataclass(frozen=True)
class AgentEvaluationRun:
    provenance: Provenance
    scores: tuple[TranscriptScore, ...]
    metrics: AgentMetrics
    gate: tuple[Any, ...] = field(default_factory=tuple)
    #: Where the scorer disagreed with what a fixture said it planted.
    detection_mismatches: tuple[str, ...] = ()
    #: True when the corpus deliberately contains defects, in which case gate
    #: failure is the expected outcome and says nothing about the agent.
    adversarial: bool = False

    @property
    def gate_passed(self) -> bool:
        return all(check.passed for check in self.gate)

    @property
    def detection_verified(self) -> bool:
        """Every planted defect found, and none invented."""
        return not self.detection_mismatches

    @property
    def baseline_only(self) -> bool:
        """True when nothing here may be used to pass GATE-AGENT-MVP."""
        return not self.provenance.is_real_model

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "provenance": self.provenance.as_dict(),
            "adversarial_corpus": self.adversarial,
            "detection_verified": self.detection_verified,
            "detection_mismatches": list(self.detection_mismatches),
            "gate_would_pass": self.gate_passed,
            "sufficient_for_gate_agent_mvp": (
                self.gate_passed and not self.baseline_only and not self.adversarial
            ),
            "gate": [check.as_dict() for check in self.gate],
            "metrics": self.metrics.as_dict(),
            "transcripts": [item.as_dict() for item in self.scores],
        }


def pooled(ratios: list[Ratio]) -> Ratio:
    return total(ratios)
