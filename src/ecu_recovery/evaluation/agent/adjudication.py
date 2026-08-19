"""Post-freeze adjudication: judgements that arrive after the transcript is fixed.

Some properties are not decidable from a transcript. Whether a claim is *true*,
whether it names the right role, and whether being wrong about it would matter
are semantic questions, and `EVALS.md` reserves those for blinded human
reviewers rather than for code.

They still need somewhere to live, and that place must not be the transcript.
The sequence is fixed:

    model output -> freeze transcript -> reveal ground truth / adjudicate
        -> deterministic scoring

so an adjudication is a separate document keyed by transcript id. A transcript
never changes when judgement arrives, which is what keeps "the model said this"
and "a reviewer concluded that" from blurring into each other.

Authored adjudications exist to prove the scorer computes these metrics
correctly. They are labelled as authored and they do not make a run a baseline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class AdjudicationError(ValueError):
    """An adjudication file is malformed or contradicts its transcript."""


@dataclass(frozen=True)
class ClaimJudgement:
    """One reviewer's verdict on one claim.

    Every field is optional and defaults to unjudged. A missing verdict is not a
    negative one: "nobody looked" and "somebody looked and said no" are
    different, and collapsing them is how an unmeasured property starts looking
    like a measured zero.
    """

    claim_index: int
    semantically_supported: bool | None = None
    classification_correct: bool | None = None
    critical: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_index": self.claim_index,
            "semantically_supported": self.semantically_supported,
            "classification_correct": self.classification_correct,
            "critical": self.critical,
        }


@dataclass(frozen=True)
class Adjudication:
    transcript_id: str
    adjudicator: str
    judgements: tuple[ClaimJudgement, ...] = field(default_factory=tuple)

    def for_claim(self, index: int) -> ClaimJudgement | None:
        return next((item for item in self.judgements if item.claim_index == index), None)

    @property
    def is_human(self) -> bool:
        return self.adjudicator == "human"

    def as_dict(self) -> dict[str, Any]:
        return {
            "transcript_id": self.transcript_id,
            "adjudicator": self.adjudicator,
            "judgements": [item.as_dict() for item in self.judgements],
        }


def parse_adjudication(payload: dict[str, Any]) -> Adjudication:
    for name in ("transcript_id", "adjudicator"):
        if name not in payload:
            raise AdjudicationError(f"adjudication is missing {name!r}")
    judgements = []
    for raw in payload.get("judgements", []):
        if "claim_index" not in raw:
            raise AdjudicationError(f"{payload['transcript_id']}: a judgement has no claim_index")
        judgements.append(
            ClaimJudgement(
                claim_index=int(raw["claim_index"]),
                semantically_supported=raw.get("semantically_supported"),
                classification_correct=raw.get("classification_correct"),
                critical=raw.get("critical"),
            )
        )
    return Adjudication(
        transcript_id=str(payload["transcript_id"]),
        adjudicator=str(payload["adjudicator"]),
        judgements=tuple(sorted(judgements, key=lambda item: item.claim_index)),
    )


def load_adjudications(directory: Path | None) -> dict[str, Adjudication]:
    """Every adjudication in a directory, keyed by transcript id.

    A missing directory is not an error. Nothing being adjudicated yet is the
    normal state, and the metrics that need judgement report themselves as
    unmeasured rather than defaulting to a flattering number.
    """
    if directory is None or not directory.is_dir():
        return {}
    found: dict[str, Adjudication] = {}
    for path in sorted(directory.glob("*.json")):
        adjudication = parse_adjudication(json.loads(path.read_text(encoding="utf-8")))
        if adjudication.transcript_id in found:
            raise AdjudicationError(f"two adjudications for {adjudication.transcript_id}")
        found[adjudication.transcript_id] = adjudication
    return found
