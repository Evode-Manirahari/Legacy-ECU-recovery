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
from typing import Any, ClassVar

from ..models import Ratio, total

SCHEMA_VERSION = 1

#: A claim asserting something about the program, as opposed to admitting it
#: cannot tell. Only these carry an evidential burden.
FACTUAL_SUPPORT = ("observed", "inferred")


@dataclass(frozen=True)
class Measurement:
    """A metric, or an honest statement that nobody has measured it.

    Unmeasured is not zero and not a pass. A metric that needs semantic
    judgement and has not received any reports itself as unmeasured, carries the
    reason, and cannot satisfy a gate: a green line nobody computed is worse
    than a red one, because it stops anyone looking.
    """

    name: str
    ratio: Ratio | None = None
    count: int | None = None
    value: float | None = None
    measured: bool = True
    reason: str = ""
    #: Adjudicated units over available units. A ratio publishes its own
    #: denominator, but "3/5 subjects correct" does not say how many subjects
    #: went unjudged, and a partial semantic measurement must not read as a
    #: full-corpus one.
    coverage: Ratio | None = None
    #: How the judgement behind this number was obtained. Only a reconciled
    #: two-reviewer verdict may satisfy a gate; an authored label can compute a
    #: number for testing the scorer and nothing more.
    provenance: str = "derived"

    @classmethod
    def unmeasured(cls, name: str, reason: str) -> Measurement:
        return cls(name=name, measured=False, reason=reason, provenance="none")

    @property
    def gate_eligible(self) -> bool:
        return self.measured and self.provenance in ("derived", "human-quorum")

    def render(self) -> str:
        if not self.measured:
            return "UNMEASURED"
        if self.count is not None:
            return str(self.count)
        if self.value is not None:
            return f"{self.value:.4f}"
        return "n/a" if self.ratio is None else self.ratio.render()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "measured": self.measured,
            "provenance": self.provenance,
            "gate_eligible": self.gate_eligible,
            "reason": self.reason,
            "ratio": None if self.ratio is None else self.ratio.as_dict(),
            "count": self.count,
            "value": self.value,
            "coverage": None if self.coverage is None else self.coverage.as_dict(),
        }


@dataclass(frozen=True)
class DetectorVector:
    """Every field the scorer can report about one transcript.

    Complete on purpose. Comparing only the fields a fixture happened to mention
    would catch a missed defect but never an invented one, and "no false
    positives" is half of what a detector has to prove.
    """

    parsed: bool
    claims: int
    factual_claims: int
    raw_factual_claims: int
    citations: int
    valid_citations: int
    fabricated_citations: int
    unsupported_factual_claims: int
    demotions: int

    FIELDS: ClassVar[tuple[str, ...]] = (
        "parsed",
        "claims",
        "factual_claims",
        "raw_factual_claims",
        "citations",
        "valid_citations",
        "fabricated_citations",
        "unsupported_factual_claims",
        "demotions",
    )

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.FIELDS}


@dataclass(frozen=True)
class ClassificationScore:
    """A lexical proxy for whether a claim describes the right role.

    A **diagnostic**, not classification accuracy. Term overlap between a
    sentence a model wrote and a sentence a fixture author wrote says something
    about vocabulary and nothing about whether the model identified the right
    role. EVALS.md reserves that judgement for two blinded reviewers, so
    classification accuracy is reported as unmeasured until one exists, and this
    is published beside it under a name that cannot be mistaken for it.
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
class CalibrationBucket:
    """One confidence band, with the gap that calibration is actually about.

    Accuracy answers "how often is it right". Calibration answers "when it says
    0.9, is it right about nine times in ten". Two runs can share the first and
    differ completely in the second, which is why an accuracy rate must never be
    published under this name.
    """

    lower: float
    upper: float
    claims: int
    correct: int
    mean_confidence: float

    @property
    def accuracy(self) -> float:
        return self.correct / self.claims if self.claims else 0.0

    @property
    def gap(self) -> float:
        """Signed. Positive means the band was overconfident."""
        return round(self.mean_confidence - self.accuracy, 6)

    def as_dict(self) -> dict[str, Any]:
        return {
            "range": [self.lower, self.upper],
            "claims": self.claims,
            "correct": self.correct,
            "mean_confidence": round(self.mean_confidence, 6),
            "accuracy": round(self.accuracy, 6),
            "gap": self.gap,
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
    raw_factual_claims: int
    demotions: int
    classification: ClassificationScore | None = None
    notes: tuple[str, ...] = ()

    @property
    def detector(self) -> DetectorVector:
        return DetectorVector(
            parsed=self.parsed,
            claims=self.claims,
            factual_claims=self.factual_claims,
            raw_factual_claims=self.raw_factual_claims,
            citations=self.citations,
            valid_citations=self.valid_citations,
            fabricated_citations=self.fabricated_citations,
            unsupported_factual_claims=self.unsupported_factual_claims,
            demotions=self.demotions,
        )

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
            "raw_factual_claims": self.raw_factual_claims,
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
    #: Model overreach, counted before AGENT-001 demoted it. A claim the agent
    #: caught is still a claim the model made.
    unsupported_factual_claims: Ratio
    tool_hallucinations: int
    critical_unsupported_claims: Measurement
    classification_accuracy: Measurement
    confidence_calibration: Measurement
    classification_term_recall_diagnostic: Ratio
    citation_support_calibration: tuple[ConfidenceBucket, ...] = ()
    calibration_buckets: tuple[CalibrationBucket, ...] = ()
    review_disagreements: tuple[str, ...] = ()
    transcripts: int = 0
    demotions: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "transcripts": self.transcripts,
            "evidence_reference_validity": self.evidence_reference_validity.as_dict(),
            "schema_compliance": self.schema_compliance.as_dict(),
            "unsupported_factual_claims_raw": self.unsupported_factual_claims.as_dict(),
            "tool_hallucinations": self.tool_hallucinations,
            "critical_unsupported_claims": self.critical_unsupported_claims.as_dict(),
            "demotions": self.demotions,
            "classification_accuracy": self.classification_accuracy.as_dict(),
            "classification_term_recall_diagnostic": (
                self.classification_term_recall_diagnostic.as_dict()
            ),
            "confidence_calibration": self.confidence_calibration.as_dict(),
            "citation_support_calibration": [
                item.as_dict() for item in self.citation_support_calibration
            ],
            "calibration_buckets": [item.as_dict() for item in self.calibration_buckets],
            "review_disagreements": list(self.review_disagreements),
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
    #: Who supplied the post-freeze judgements, if anyone. Authored labels
    #: verify that the scorer computes adjudicated metrics; they are not review.
    adjudicators: tuple[str, ...] = ()

    @property
    def gate_passed(self) -> bool:
        return all(check.passed for check in self.gate)

    @property
    def detection_verified(self) -> bool:
        """Every planted defect found, and none invented."""
        return not self.detection_mismatches

    @property
    def baseline_only(self) -> bool:
        """True when nothing here may be used to pass GATE-AGENT-MVP.

        Authored adjudication counts as authored, exactly like an authored
        transcript. A label written to test the scorer is not a reviewer's
        verdict, and treating it as one would let the evaluator grade its own
        homework.
        """
        return not self.provenance.is_real_model or any(
            item != "human" for item in self.adjudicators
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "provenance": self.provenance.as_dict(),
            "adversarial_corpus": self.adversarial,
            "adjudicators": list(self.adjudicators),
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
