"""Post-freeze adjudication by independent reviewers.

Some properties are not decidable from a transcript. Whether a claim is true,
whether the function was classified correctly, and whether being wrong would
matter are semantic questions, and `EVALS.md` reserves them for **two blinded
reviewers** whose scores are reconciled.

Three things follow from that, and each is a rule here rather than a convention.

A review carries a **reviewer identity**. Two files from one reviewer are one
opinion, so quorum counts distinct reviewers and a duplicate submission is
rejected rather than quietly doubling someone's vote.

**Disagreement stays visible.** Where reviewers differ, the label is not
resolved by picking one or by averaging; the claim is left unjudged and the
disagreement is recorded. Silently choosing a side would turn a contested
judgement into a measurement.

**Classification is judged once per subject.** A function that provoked five
claims must not get five votes while another gets one, so classification is a
transcript-level verdict rather than a per-claim one.

Adjudications live beside the transcript, never inside it, which keeps the
sequence intact: model output, freeze, independent review, deterministic
scoring.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: `EVALS.md`: two blinded reviewers, reconciled.
REQUIRED_HUMAN_REVIEWERS = 2

KIND_HUMAN = "human"
KIND_AUTHORED = "authored"


class AdjudicationError(ValueError):
    """A review is malformed, or two reviews claim the same reviewer."""


@dataclass(frozen=True)
class ClaimJudgement:
    """One reviewer's verdict on one claim.

    Both fields default to unjudged. "Nobody looked" and "somebody looked and
    said no" are different, and collapsing them is how an unmeasured property
    starts reading as a measured zero.
    """

    claim_index: int
    semantically_supported: bool | None = None
    critical: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_index": self.claim_index,
            "semantically_supported": self.semantically_supported,
            "critical": self.critical,
        }


@dataclass(frozen=True)
class Review:
    """One reviewer's complete verdict on one transcript."""

    transcript_id: str
    reviewer: str
    kind: str = KIND_AUTHORED
    #: Subject-level, exactly one per review. Not per claim.
    classification_correct: bool | None = None
    judgements: tuple[ClaimJudgement, ...] = field(default_factory=tuple)

    @property
    def is_human(self) -> bool:
        return self.kind == KIND_HUMAN

    def for_claim(self, index: int) -> ClaimJudgement | None:
        return next((item for item in self.judgements if item.claim_index == index), None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "transcript_id": self.transcript_id,
            "reviewer": self.reviewer,
            "kind": self.kind,
            "classification_correct": self.classification_correct,
            "judgements": [item.as_dict() for item in self.judgements],
        }


@dataclass(frozen=True)
class Verdict:
    """A reconciled label, or an explicit statement that there is not one."""

    value: bool | None
    reviewers: int
    disagreed: bool = False

    @property
    def settled(self) -> bool:
        return self.value is not None and not self.disagreed


@dataclass(frozen=True)
class ReviewPanel:
    """Every review, grouped, with a stated reconciliation policy.

    The policy is unanimity among the reviewers who expressed an opinion. It is
    deliberately the strictest available: with two reviewers, "reconciled" and
    "agreed" are the same thing, and anything looser would be this code deciding
    a semantic question it is not qualified to decide.
    """

    reviews: tuple[Review, ...] = ()

    def _for(self, transcript_id: str, human_only: bool = True) -> list[Review]:
        return [
            review
            for review in self.reviews
            if review.transcript_id == transcript_id and (review.is_human or not human_only)
        ]

    def reviewer_count(self, transcript_id: str, human_only: bool = True) -> int:
        return len({review.reviewer for review in self._for(transcript_id, human_only)})

    def has_quorum(self, transcript_id: str) -> bool:
        """Two distinct *human* reviewers. Authored labels never count."""
        return self.reviewer_count(transcript_id) >= REQUIRED_HUMAN_REVIEWERS

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted({review.kind for review in self.reviews}))

    @property
    def fully_human(self) -> bool:
        return bool(self.reviews) and all(review.is_human for review in self.reviews)

    def _reconcile(self, opinions: list[bool]) -> Verdict:
        if not opinions:
            return Verdict(value=None, reviewers=0)
        if len(set(opinions)) > 1:
            return Verdict(value=None, reviewers=len(opinions), disagreed=True)
        return Verdict(value=opinions[0], reviewers=len(opinions))

    def claim_support(self, transcript_id: str, claim_index: int) -> Verdict:
        opinions = [
            judgement.semantically_supported
            for review in self._for(transcript_id, human_only=False)
            if (judgement := review.for_claim(claim_index)) is not None
            and judgement.semantically_supported is not None
        ]
        return self._reconcile(opinions)

    def claim_criticality(self, transcript_id: str, claim_index: int) -> Verdict:
        opinions = [
            judgement.critical
            for review in self._for(transcript_id, human_only=False)
            if (judgement := review.for_claim(claim_index)) is not None
            and judgement.critical is not None
        ]
        return self._reconcile(opinions)

    def classification(self, transcript_id: str) -> Verdict:
        """One verdict per subject, however many claims the transcript held."""
        opinions = [
            review.classification_correct
            for review in self._for(transcript_id, human_only=False)
            if review.classification_correct is not None
        ]
        return self._reconcile(opinions)

    def disagreements(self, transcript_id: str, claims: int) -> tuple[str, ...]:
        found: list[str] = []
        if self.classification(transcript_id).disagreed:
            found.append(f"{transcript_id}: reviewers disagree on classification")
        for index in range(claims):
            if self.claim_support(transcript_id, index).disagreed:
                found.append(f"{transcript_id}: reviewers disagree on claim {index} support")
            if self.claim_criticality(transcript_id, index).disagreed:
                found.append(f"{transcript_id}: reviewers disagree on claim {index} criticality")
        return tuple(found)


def parse_review(payload: dict[str, Any]) -> Review:
    for name in ("transcript_id", "reviewer"):
        if name not in payload:
            raise AdjudicationError(f"review is missing {name!r}")
    judgements = []
    for raw in payload.get("judgements", []):
        if "claim_index" not in raw:
            raise AdjudicationError(f"{payload['transcript_id']}: a judgement has no claim_index")
        judgements.append(
            ClaimJudgement(
                claim_index=int(raw["claim_index"]),
                semantically_supported=raw.get("semantically_supported"),
                critical=raw.get("critical"),
            )
        )
    return Review(
        transcript_id=str(payload["transcript_id"]),
        reviewer=str(payload["reviewer"]),
        kind=str(payload.get("kind", KIND_AUTHORED)),
        classification_correct=payload.get("classification_correct"),
        judgements=tuple(sorted(judgements, key=lambda item: item.claim_index)),
    )


def load_panel(directory: Path | None) -> ReviewPanel:
    """Every review in a directory. Several per transcript is the normal case.

    A repeated `(transcript, reviewer)` pair is refused: one person filing twice
    is one opinion, and letting it through would manufacture quorum out of a
    single reviewer.
    """
    if directory is None or not directory.is_dir():
        return ReviewPanel()
    seen: dict[tuple[str, str], Path] = {}
    reviews: list[Review] = []
    for path in sorted(directory.glob("*.json")):
        review = parse_review(json.loads(path.read_text(encoding="utf-8")))
        key = (review.transcript_id, review.reviewer)
        if key in seen:
            raise AdjudicationError(
                f"{review.reviewer} reviewed {review.transcript_id} twice "
                f"({seen[key].name} and {path.name}); one reviewer is one opinion"
            )
        seen[key] = path
        reviews.append(review)
    grouped: dict[str, int] = defaultdict(int)
    for review in reviews:
        grouped[review.transcript_id] += 1
    return ReviewPanel(reviews=tuple(reviews))
