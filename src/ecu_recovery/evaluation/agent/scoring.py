"""Score frozen transcripts against hidden ground truth.

Six of the seven metrics are decidable from the transcript alone, because
`AGENT-001` already recorded the verdict on every citation. That is the point of
having it record them: whether a citation resolved is a fact about a tool
replay, not a judgement, and scoring should not be re-deriving it with different
code that might disagree.

The seventh, classification, needs the answer key, and it is where honesty costs
something. Comparing a sentence a model wrote against a sentence a fixture
author wrote is a semantic judgement, and EVALS.md reserves those for two
blinded human reviewers. What is implemented instead is term recall - a stated,
crude, lexical proxy - published as a baseline and never gated. A number with a
disclosed definition can be argued with; an absent number gets assumed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..groundtruth import DEFAULT_SAMPLES_ROOT
from ..models import Ratio
from .adjudication import ReviewPanel
from .models import (
    FACTUAL_SUPPORT,
    AgentMetrics,
    CalibrationBucket,
    ClassificationScore,
    ConfidenceBucket,
    DetectorVector,
    Measurement,
    TranscriptScore,
    pooled,
)
from .transcripts import Transcript

#: Words carrying no discriminating power in a role description. Only entries
#: longer than three characters are listed, because `_terms` already drops
#: anything shorter.
_STOPWORDS = frozenset(
    [
        "each",
        "from",
        "have",
        "into",
        "only",
        "that",
        "then",
        "this",
        "value",
        "values",
        "when",
        "with",
        "within",
    ]
)

#: Confidence buckets for calibration. Ten would be the eventual shape; four
#: keeps every bucket populated enough to mean something at this corpus size.
_BUCKETS = ((0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0))


def _terms(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z]+", text.lower())
        if len(word) > 3 and word not in _STOPWORDS
    }


def expected_roles(sample_id: str, samples_root: Path | None = None) -> dict[str, str]:
    root = samples_root or DEFAULT_SAMPLES_ROOT
    path = root / "ground_truth" / f"{sample_id}.json"
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    roles: dict[str, str] = payload.get("expected_function_roles", {})
    return roles


def score_classification(
    transcript: Transcript, role_name: str, expected_role: str
) -> ClassificationScore:
    """Term recall of the expected role across everything the agent claimed."""
    said = _terms(" ".join(str(claim.get("statement", "")) for claim in transcript.claims))
    wanted = _terms(expected_role)
    return ClassificationScore(
        subject=transcript.subject,
        expected_role=role_name,
        matched_terms=tuple(sorted(wanted & said)),
        missed_terms=tuple(sorted(wanted - said)),
    )


def score_transcript(
    transcript: Transcript,
    role_name: str | None = None,
    role_text: str | None = None,
) -> TranscriptScore:
    """Score one transcript. Everything here is decidable; nothing is judged.

    Unsupported factual claims are counted **before** demotion. AGENT-001
    demotes a claim whose citations do not hold, which is the right behaviour
    and would make this metric read zero if it only looked at survivors - the
    agent catching an overreach is not the model declining to make one. Each
    recorded demotion was a factual claim that failed evidential checking, so it
    counts, and a survivor that is still unsupported counts too. The two sets
    are disjoint: a demoted claim now carries `unknown`, so it is no longer
    factual and cannot be counted twice.
    """
    checks = transcript.checks
    claims = transcript.claims
    surviving_factual = [claim for claim in claims if claim.get("support") in FACTUAL_SUPPORT]

    valid = sum(1 for item in checks if item.get("resolved"))
    fabricated = sum(1 for item in checks if item.get("fabricated"))

    by_fact_id = {item.get("fact_id"): item for item in checks}
    still_unsupported = 0
    for claim in surviving_factual:
        citations = list(claim.get("citations", []))
        if not citations:
            still_unsupported += 1
            continue
        if not all(
            by_fact_id.get(citation.get("fact_id"), {}).get("resolved", False)
            for citation in citations
        ):
            still_unsupported += 1

    demoted = len(transcript.demotions)
    unsupported = demoted + still_unsupported
    raw_factual = len(surviving_factual) + demoted

    classification = None
    if role_name is not None and role_text is not None:
        classification = score_classification(transcript, role_name, role_text)

    notes: list[str] = []
    if not transcript.parsed:
        notes.append(str(transcript.investigation.get("failure", "unusable reply")))

    return TranscriptScore(
        transcript_id=transcript.id,
        sample_id=transcript.sample_id,
        subject=transcript.subject,
        scenario=transcript.scenario,
        parsed=transcript.parsed,
        claims=len(claims),
        factual_claims=len(surviving_factual),
        citations=len(checks),
        valid_citations=valid,
        fabricated_citations=fabricated,
        unsupported_factual_claims=unsupported,
        raw_factual_claims=raw_factual,
        demotions=demoted,
        classification=classification,
        notes=tuple(notes),
    )


def confidence_buckets(transcripts: tuple[Transcript, ...]) -> tuple[ConfidenceBucket, ...]:
    """Stated confidence against observed support, where any claims fall.

    Support is "every citation on this claim resolved", which is the only notion
    of correctness available without a human. Empty buckets are dropped rather
    than published as zeroes: a bucket nobody landed in says nothing.
    """
    buckets: list[ConfidenceBucket] = []
    for lower, upper in _BUCKETS:
        claims = 0
        supported = 0
        for transcript in transcripts:
            by_fact_id = {item.get("fact_id"): item for item in transcript.checks}
            for claim in transcript.claims:
                if claim.get("support") not in FACTUAL_SUPPORT:
                    continue
                confidence = float(claim.get("confidence", 0.0))
                inside = lower <= confidence < upper or (upper == 1.0 and confidence == 1.0)
                if not inside:
                    continue
                claims += 1
                citations = list(claim.get("citations", []))
                if citations and all(
                    by_fact_id.get(citation.get("fact_id"), {}).get("resolved", False)
                    for citation in citations
                ):
                    supported += 1
        if claims:
            buckets.append(ConfidenceBucket(lower, upper, claims, supported))
    return tuple(buckets)


_NO_REVIEW = (
    "semantic adjudication is required and none has been supplied; EVALS.md "
    "reserves this judgement for two blinded reviewers"
)
_NO_QUORUM = (
    "fewer than two distinct human reviewers; authored labels verify the scorer "
    "and never satisfy review quorum"
)


def _provenance(panel: ReviewPanel, transcript_ids: list[str]) -> str:
    if panel.fully_human and all(panel.has_quorum(item) for item in transcript_ids):
        return "human-quorum"
    return "authored"


def critical_unsupported_claims(
    transcripts: tuple[Transcript, ...], panel: ReviewPanel
) -> Measurement:
    """Claims that are **both** critical and semantically unsupported.

    Both halves matter. A critical claim that is true is not a failure, and an
    unsupported claim nobody would act on is a different and lesser problem.
    Counting either alone would report a number under a name that means
    something else.

    A claim missing either verdict leaves the count a lower bound rather than a
    count, so the measurement reports itself incomplete instead of quietly
    settling for what it happens to know.
    """
    counted = 0
    fully_judged = 0
    partial = 0
    for transcript in transcripts:
        for index in range(len(transcript.claims)):
            support = panel.claim_support(transcript.id, index)
            criticality = panel.claim_criticality(transcript.id, index)
            if support.settled and criticality.settled:
                fully_judged += 1
                if criticality.value and not support.value:
                    counted += 1
            elif support.settled or criticality.settled:
                partial += 1
    if fully_judged == 0:
        return Measurement.unmeasured("critical_unsupported_claims", _NO_REVIEW)
    if partial:
        return Measurement.unmeasured(
            "critical_unsupported_claims",
            f"{partial} claim(s) carry only one of support and criticality, so the "
            "count would be a lower bound rather than a count",
        )
    ids = [item.id for item in transcripts]
    provenance = _provenance(panel, ids)
    return Measurement(
        "critical_unsupported_claims",
        count=counted,
        provenance=provenance,
        reason="" if provenance == "human-quorum" else _NO_QUORUM,
    )


def classification_accuracy(transcripts: tuple[Transcript, ...], panel: ReviewPanel) -> Measurement:
    """One verdict per subject, not one per claim.

    A function that provoked five claims must not outvote one that provoked a
    single claim; the question is whether the function was identified, and there
    is exactly one answer to it per function.
    """
    correct = 0
    judged = 0
    for transcript in transcripts:
        verdict = panel.classification(transcript.id)
        if not verdict.settled:
            continue
        judged += 1
        correct += 1 if verdict.value else 0
    if judged == 0:
        return Measurement.unmeasured("classification_accuracy", _NO_REVIEW)
    ids = [item.id for item in transcripts]
    provenance = _provenance(panel, ids)
    return Measurement(
        "classification_accuracy",
        ratio=Ratio(correct, judged),
        provenance=provenance,
        reason="" if provenance == "human-quorum" else _NO_QUORUM,
    )


def calibration_buckets(
    transcripts: tuple[Transcript, ...], panel: ReviewPanel
) -> tuple[CalibrationBucket, ...]:
    """Stated confidence against adjudicated correctness, per band."""
    buckets: list[CalibrationBucket] = []
    for lower, upper in _BUCKETS:
        confidences: list[float] = []
        correct = 0
        for transcript in transcripts:
            for index, claim in enumerate(transcript.claims):
                verdict = panel.claim_support(transcript.id, index)
                if not verdict.settled:
                    continue
                confidence = float(claim.get("confidence", 0.0))
                inside = lower <= confidence < upper or (upper == 1.0 and confidence == 1.0)
                if not inside:
                    continue
                confidences.append(confidence)
                correct += 1 if verdict.value else 0
        if confidences:
            buckets.append(
                CalibrationBucket(
                    lower=lower,
                    upper=upper,
                    claims=len(confidences),
                    correct=correct,
                    mean_confidence=sum(confidences) / len(confidences),
                )
            )
    return tuple(buckets)


def confidence_calibration(transcripts: tuple[Transcript, ...], panel: ReviewPanel) -> Measurement:
    """Expected calibration error: the weighted mean gap between stated and observed.

        ECE = sum over bands of  (band size / total) * |mean confidence - accuracy|

    Accuracy is not calibration. Two corpora can be right equally often and be
    utterly different here: one that says 0.9 when it is right and 0.1 when it is
    wrong is well calibrated, and one that says the reverse is not, though both
    score fifty percent. Publishing a correctness rate under this name would
    hide exactly that difference.

    Zero is perfect. Requires adjudicated semantic correctness.
    """
    buckets = calibration_buckets(transcripts, panel)
    if not buckets:
        return Measurement.unmeasured("confidence_calibration", _NO_REVIEW)
    total_claims = sum(item.claims for item in buckets)
    ece = sum(item.claims * abs(item.gap) for item in buckets) / total_claims
    ids = [item.id for item in transcripts]
    provenance = _provenance(panel, ids)
    return Measurement(
        "confidence_calibration",
        value=round(ece, 6),
        provenance=provenance,
        reason=(
            "expected calibration error over adjudicated semantic correctness; 0 is perfect"
            if provenance == "human-quorum"
            else _NO_QUORUM
        ),
    )


def aggregate(
    transcripts: tuple[Transcript, ...],
    scores: tuple[TranscriptScore, ...],
    panel: ReviewPanel | None = None,
) -> AgentMetrics:
    panel = panel or ReviewPanel()
    disagreements = tuple(
        item
        for transcript in transcripts
        for item in panel.disagreements(transcript.id, len(transcript.claims))
    )
    return AgentMetrics(
        evidence_reference_validity=Ratio(
            sum(item.valid_citations for item in scores),
            sum(item.citations for item in scores),
        ),
        schema_compliance=Ratio(sum(1 for item in scores if item.parsed), len(scores)),
        unsupported_factual_claims=Ratio(
            sum(item.unsupported_factual_claims for item in scores),
            sum(item.raw_factual_claims for item in scores),
        ),
        tool_hallucinations=sum(item.fabricated_citations for item in scores),
        critical_unsupported_claims=critical_unsupported_claims(transcripts, panel),
        classification_accuracy=classification_accuracy(transcripts, panel),
        confidence_calibration=confidence_calibration(transcripts, panel),
        classification_term_recall_diagnostic=pooled(
            [item.classification.recall for item in scores if item.classification is not None]
        ),
        citation_support_calibration=confidence_buckets(transcripts),
        calibration_buckets=calibration_buckets(transcripts, panel),
        review_disagreements=disagreements,
        transcripts=len(scores),
        demotions=sum(item.demotions for item in scores),
    )


def verify_detection(transcript: Transcript, score: TranscriptScore) -> tuple[str, ...]:
    """Compare the complete detector vector against the complete expectation.

    Complete on both sides, because comparing only the fields a fixture chose to
    mention catches a missed defect and never an invented one. A fixture must
    declare every field; an omission is a fixture bug and is reported as one,
    not silently treated as agreement.
    """
    observed = score.detector.as_dict()
    expected = dict(transcript.expects)
    if not expected:
        return (f"{transcript.id}: fixture declares no detector expectations",)

    mismatches: list[str] = []
    for name in sorted(set(expected) - set(observed)):
        mismatches.append(f"{transcript.id}: fixture expects unknown field {name!r}")
    for name in DetectorVector.FIELDS:
        if name not in expected:
            mismatches.append(
                f"{transcript.id}: fixture declares no expectation for {name!r}; "
                "the vector must be complete or a false positive there is invisible"
            )
            continue
        if observed[name] != expected[name]:
            mismatches.append(
                f"{transcript.id}: expected {name}={expected[name]!r}, "
                f"scorer found {observed[name]!r}"
            )
    return tuple(mismatches)
