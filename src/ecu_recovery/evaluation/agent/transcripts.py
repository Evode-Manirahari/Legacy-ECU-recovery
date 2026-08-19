"""Frozen investigation transcripts.

A transcript is one completed investigation, serialized: the fact sheet that was
gathered, the claims that came back, and the verdict on every citation. Freezing
it is what makes evaluation deterministic and free to re-run - scoring reads
JSON, needs no Ghidra, no model, and no network, so the numbers can be
recomputed on any machine at any time.

It also separates two questions that would otherwise be entangled. Re-running
the scorer over a fixed transcript measures the scorer. Re-running the agent
produces a new transcript and measures the agent. Keeping them apart is the only
way to tell a scoring change from a model change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TRANSCRIPT_SCHEMA_VERSION = 1


class TranscriptError(ValueError):
    """A transcript is missing, malformed, or not the shape scoring expects."""


@dataclass(frozen=True)
class Transcript:
    """One frozen investigation, plus what it was an investigation of."""

    id: str
    sample_id: str
    subject: str
    scenario: str
    investigation: dict[str, Any]
    provenance: str = "authored"
    #: What this fixture deliberately plants, so the scorer can be checked
    #: against it. A detector that never meets a defect proves nothing, and one
    #: that meets a defect it was not told about proves nothing either.
    expects: dict[str, Any] = field(default_factory=dict)

    @property
    def parsed(self) -> bool:
        """Whether the reply was usable at all. A failure is a real outcome."""
        return self.investigation.get("failure") is None

    @property
    def claims(self) -> list[dict[str, Any]]:
        return list(self.investigation.get("claims", []))

    @property
    def checks(self) -> list[dict[str, Any]]:
        return list(self.investigation.get("citation_checks", []))

    @property
    def demotions(self) -> list[str]:
        return list(self.investigation.get("demotions", []))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TRANSCRIPT_SCHEMA_VERSION,
            "id": self.id,
            "sample_id": self.sample_id,
            "subject": self.subject,
            "scenario": self.scenario,
            "provenance": self.provenance,
            "expects": dict(self.expects),
            "investigation": self.investigation,
        }


_REQUIRED = ("id", "sample_id", "subject", "scenario", "investigation")


def parse_transcript(payload: dict[str, Any]) -> Transcript:
    missing = [name for name in _REQUIRED if name not in payload]
    if missing:
        raise TranscriptError(f"transcript is missing {missing}")
    investigation = payload["investigation"]
    if not isinstance(investigation, dict):
        raise TranscriptError(f"{payload['id']}: investigation must be an object")
    return Transcript(
        id=str(payload["id"]),
        sample_id=str(payload["sample_id"]),
        subject=str(payload["subject"]),
        scenario=str(payload["scenario"]),
        investigation=investigation,
        provenance=str(payload.get("provenance", "authored")),
        expects=dict(payload.get("expects", {})),
    )


def load_transcripts(directory: Path) -> tuple[Transcript, ...]:
    """Every transcript in a directory, ordered by id.

    Ordered because the report lists them and an unstable order would make two
    identical runs produce different artifacts.
    """
    if not directory.is_dir():
        raise TranscriptError(f"no transcript directory at {directory}")
    transcripts = [
        parse_transcript(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*.json"))
    ]
    if not transcripts:
        raise TranscriptError(f"no transcripts found in {directory}")
    return tuple(sorted(transcripts, key=lambda item: item.id))
