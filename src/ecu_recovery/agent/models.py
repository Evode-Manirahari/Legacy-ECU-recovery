"""What the investigator produces, and what it is allowed to say.

Three ideas carry this file.

A **fact** is something a tool returned, recorded with the exact call that
returned it. Facts are gathered before the model is involved and are the only
material it is given.

A **citation** points at a fact by id. It is checkable twice over: the id must
belong to a fact that was actually gathered, and re-running that fact's call
must produce *the same result*. Success alone is not reproduction - a tool can
succeed and return something else - so each fact records a digest of the
canonical result it came from and replay compares against it. Citing a tool call
that was never issued is therefore detectable, and so is citing one whose answer
has moved.

A **claim** is an interpretation, and it carries how well supported it is.
`OBSERVED` requires a citation that survives checking. `UNKNOWN` is a first-class
answer, not a failure to produce one - a system that cannot say "I do not know"
will say something else instead, and that is worse.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


def canonical_digest(payload: Any) -> str:
    """A stable fingerprint of a tool result.

    Sorted keys and no incidental whitespace, so two runs that returned the same
    data agree byte for byte regardless of dict ordering. Truncated to sixteen
    hex characters: this identifies a result, it does not defend against an
    adversary constructing a collision.
    """
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]


def subject_tag(subject: str) -> str:
    """The subject, as it appears inside an evidence key."""
    return subject[2:] if subject.startswith("0x") else subject


class SupportLevel(StrEnum):
    """How far a claim stands from the evidence.

    Mirrors `Certainty` in the evidence model rather than inventing a second
    vocabulary: OBSERVED maps to KNOWN, INFERRED to INFERRED, UNKNOWN to UNKNOWN.
    """

    OBSERVED = "observed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Fact:
    """One tool result, with the call that produced it and a digest of it.

    `id` stays short - the model has to copy it into a citation, and every extra
    character is a chance to mistype one. Persistence needs global identity
    instead, so `evidence_key` scopes the same fact by subject. Both derive from
    here so nothing downstream can invent a second convention.
    """

    id: str
    tool: str
    arguments: dict[str, Any]
    subject: str
    summary: str
    result_digest: str = ""

    @property
    def evidence_key(self) -> str:
        """Globally unique within a binary. Two subjects never collide."""
        return f"E-{subject_tag(self.subject)}-{self.id}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "evidence_key": self.evidence_key,
            "tool": self.tool,
            "arguments": dict(self.arguments),
            "subject": self.subject,
            "summary": self.summary,
            "result_digest": self.result_digest,
        }


@dataclass(frozen=True)
class FactSheet:
    """Everything gathered about one subject, in a stable order."""

    subject: str
    facts: tuple[Fact, ...]
    refusals: tuple[tuple[str, str], ...] = ()

    def by_id(self, fact_id: str) -> Fact | None:
        return next((item for item in self.facts if item.id == fact_id), None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "facts": [item.as_dict() for item in self.facts],
            "refusals": [{"tool": tool, "error": error} for tool, error in self.refusals],
        }


@dataclass(frozen=True)
class Citation:
    fact_id: str
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"fact_id": self.fact_id, "note": self.note}


@dataclass(frozen=True)
class CitationCheck:
    """The verdict on one citation, and why."""

    citation: Citation
    resolved: bool
    reason: str
    fabricated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.citation.fact_id,
            "resolved": self.resolved,
            "fabricated": self.fabricated,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Claim:
    subject: str
    statement: str
    support: SupportLevel
    citations: tuple[Citation, ...] = ()
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not self.statement.strip():
            raise ValueError("a claim must say something")

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "statement": self.statement,
            "support": self.support.value,
            "confidence": self.confidence,
            "citations": [item.as_dict() for item in self.citations],
        }


@dataclass(frozen=True)
class Investigation:
    """One subject, investigated: what was gathered, said, and checked."""

    subject: str
    fact_sheet: FactSheet
    claims: tuple[Claim, ...] = ()
    checks: tuple[CitationCheck, ...] = ()
    demotions: tuple[str, ...] = ()
    model_provider: str = "unconfigured"
    model_name: str = "unconfigured"
    failure: str | None = None

    @property
    def fabricated_citations(self) -> tuple[CitationCheck, ...]:
        """Citations naming a call the agent never made. A critical failure."""
        return tuple(item for item in self.checks if item.fabricated)

    @property
    def unresolved_citations(self) -> tuple[CitationCheck, ...]:
        return tuple(item for item in self.checks if not item.resolved)

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "fact_sheet": self.fact_sheet.as_dict(),
            "claims": [item.as_dict() for item in self.claims],
            "citation_checks": [item.as_dict() for item in self.checks],
            "demotions": list(self.demotions),
            "fabricated_citation_count": len(self.fabricated_citations),
            "model": {"provider": self.model_provider, "name": self.model_name},
            "failure": self.failure,
        }


@dataclass(frozen=True)
class InvestigationBudget:
    """Bounds on one investigation, so a run cannot grow without limit."""

    max_instructions: int = 64
    max_callers: int = 20
    max_callees: int = 20
    max_claims: int = 20
    max_citations_per_claim: int = 8
    decompile: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
