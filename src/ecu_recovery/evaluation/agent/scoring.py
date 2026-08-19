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
from .models import (
    FACTUAL_SUPPORT,
    AgentMetrics,
    ClassificationScore,
    ConfidenceBucket,
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
    """Score one transcript. Everything here is decidable, nothing is judged."""
    checks = transcript.checks
    claims = transcript.claims
    factual = [claim for claim in claims if claim.get("support") in FACTUAL_SUPPORT]

    valid = sum(1 for item in checks if item.get("resolved"))
    fabricated = sum(1 for item in checks if item.get("fabricated"))

    # A surviving factual claim that carries an unresolved citation, or none at
    # all, is the failure the checking exists to prevent. AGENT-001 demotes
    # these, so a non-zero count here means the mechanism did not hold - which
    # is exactly why it is gated at zero rather than at "rare".
    by_fact_id = {item.get("fact_id"): item for item in checks}
    critical = 0
    unsupported = 0
    for claim in factual:
        citations = list(claim.get("citations", []))
        if not citations:
            unsupported += 1
            critical += 1
            continue
        resolved = [
            by_fact_id.get(citation.get("fact_id"), {}).get("resolved", False)
            for citation in citations
        ]
        if not all(resolved):
            unsupported += 1
            critical += 1

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
        factual_claims=len(factual),
        citations=len(checks),
        valid_citations=valid,
        fabricated_citations=fabricated,
        unsupported_factual_claims=unsupported,
        critical_unsupported_claims=critical,
        demotions=len(transcript.demotions),
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


def aggregate(
    transcripts: tuple[Transcript, ...], scores: tuple[TranscriptScore, ...]
) -> AgentMetrics:
    return AgentMetrics(
        evidence_reference_validity=Ratio(
            sum(item.valid_citations for item in scores),
            sum(item.citations for item in scores),
        ),
        schema_compliance=Ratio(sum(1 for item in scores if item.parsed), len(scores)),
        unsupported_factual_claims=Ratio(
            sum(item.unsupported_factual_claims for item in scores),
            sum(item.factual_claims for item in scores),
        ),
        tool_hallucinations=sum(item.fabricated_citations for item in scores),
        critical_unsupported_claims=sum(item.critical_unsupported_claims for item in scores),
        classification_term_recall=pooled(
            [item.classification.recall for item in scores if item.classification is not None]
        ),
        confidence_buckets=confidence_buckets(transcripts),
        transcripts=len(scores),
        demotions=sum(item.demotions for item in scores),
    )


def verify_detection(transcript: Transcript, score: TranscriptScore) -> tuple[str, ...]:
    """Compare what a fixture planted against what the scorer found.

    This is the check that makes an adversarial corpus worth having. A run over
    such a corpus is *expected* to fail the gate - the defects are deliberate -
    so gate failure says nothing about the scorer. What says something is
    whether every planted defect was detected and no unplanted one was invented.
    """
    observed = {
        "parsed": score.parsed,
        "fabricated_citations": score.fabricated_citations,
        "unsupported_factual_claims": score.unsupported_factual_claims,
        "critical_unsupported_claims": score.critical_unsupported_claims,
        "demotions": score.demotions,
        "claims": score.claims,
    }
    mismatches: list[str] = []
    for name, expected in transcript.expects.items():
        if name not in observed:
            mismatches.append(f"{transcript.id}: fixture expects unknown field {name!r}")
            continue
        if observed[name] != expected:
            mismatches.append(
                f"{transcript.id}: expected {name}={expected!r}, scorer found {observed[name]!r}"
            )
    return tuple(mismatches)
