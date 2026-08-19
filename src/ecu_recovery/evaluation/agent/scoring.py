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
from .adjudication import Adjudication
from .models import (
    FACTUAL_SUPPORT,
    AgentMetrics,
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


_NO_ADJUDICATION = (
    "semantic adjudication is required and none has been supplied; EVALS.md "
    "reserves this judgement for blinded human reviewers"
)


def _adjudicated(
    transcripts: tuple[Transcript, ...],
    adjudications: dict[str, Adjudication],
    field: str,
) -> tuple[int, int]:
    """Count (true, judged) for one adjudicated boolean across every claim."""
    judged = 0
    positive = 0
    for transcript in transcripts:
        adjudication = adjudications.get(transcript.id)
        if adjudication is None:
            continue
        for index in range(len(transcript.claims)):
            judgement = adjudication.for_claim(index)
            if judgement is None:
                continue
            value = getattr(judgement, field)
            if value is None:
                continue
            judged += 1
            positive += 1 if value else 0
    return positive, judged


def classification_accuracy(
    transcripts: tuple[Transcript, ...], adjudications: dict[str, Adjudication]
) -> Measurement:
    correct, judged = _adjudicated(transcripts, adjudications, "classification_correct")
    if judged == 0:
        return Measurement.unmeasured("classification_accuracy", _NO_ADJUDICATION)
    return Measurement("classification_accuracy", ratio=Ratio(correct, judged))


def confidence_calibration(
    transcripts: tuple[Transcript, ...], adjudications: dict[str, Adjudication]
) -> Measurement:
    """Calibration against *semantic* correctness, not against citation resolution.

    Citations resolving says the agent quoted a real tool result. It does not
    say the claim built on it is true, which `07-wrong-classification` exists to
    demonstrate: every citation holds and the claim is wrong. So this stays
    unmeasured until semantic labels exist, and the citation-based buckets are
    published beside it under a name that says what they are.
    """
    _, judged = _adjudicated(transcripts, adjudications, "semantically_supported")
    if judged == 0:
        return Measurement.unmeasured("confidence_calibration", _NO_ADJUDICATION)
    correct_by_bucket: list[ConfidenceBucket] = []
    for lower, upper in _BUCKETS:
        claims = 0
        supported = 0
        for transcript in transcripts:
            adjudication = adjudications.get(transcript.id)
            if adjudication is None:
                continue
            for index, claim in enumerate(transcript.claims):
                judgement = adjudication.for_claim(index)
                if judgement is None or judgement.semantically_supported is None:
                    continue
                confidence = float(claim.get("confidence", 0.0))
                inside = lower <= confidence < upper or (upper == 1.0 and confidence == 1.0)
                if not inside:
                    continue
                claims += 1
                supported += 1 if judgement.semantically_supported else 0
        if claims:
            correct_by_bucket.append(ConfidenceBucket(lower, upper, claims, supported))
    total_claims = sum(item.claims for item in correct_by_bucket)
    total_supported = sum(item.supported for item in correct_by_bucket)
    return Measurement(
        "confidence_calibration",
        ratio=Ratio(total_supported, total_claims),
        reason="calibration against adjudicated semantic support",
    )


def critical_unsupported_claims(
    transcripts: tuple[Transcript, ...], adjudications: dict[str, Adjudication]
) -> Measurement:
    """Criticality is a judgement, so an unjudged corpus reports unmeasured.

    Reporting zero here without adjudication would be the most dangerous number
    in the file: a gate line reading "0 critical unsupported claims" that nobody
    ever assessed.
    """
    critical, judged = _adjudicated(transcripts, adjudications, "critical")
    if judged == 0:
        return Measurement.unmeasured("critical_unsupported_claims", _NO_ADJUDICATION)
    return Measurement("critical_unsupported_claims", count=critical)


def aggregate(
    transcripts: tuple[Transcript, ...],
    scores: tuple[TranscriptScore, ...],
    adjudications: dict[str, Adjudication] | None = None,
) -> AgentMetrics:
    adjudications = adjudications or {}
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
        critical_unsupported_claims=critical_unsupported_claims(transcripts, adjudications),
        classification_accuracy=classification_accuracy(transcripts, adjudications),
        confidence_calibration=confidence_calibration(transcripts, adjudications),
        classification_term_recall_diagnostic=pooled(
            [item.classification.recall for item in scores if item.classification is not None]
        ),
        citation_support_calibration=confidence_buckets(transcripts),
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
