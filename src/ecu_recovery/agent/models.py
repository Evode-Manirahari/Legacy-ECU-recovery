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
    data agree byte for byte regardless of dict ordering.

    The full SHA-256 is kept. Truncation was a readability choice, and it was
    the wrong one: this digest decides whether a citation still reproduces its
    fact, and a shortened hash trades collision resistance for nothing anyone
    reads. Sixty-four characters cost only screen space in a field no human
    parses.
    """
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


#: Persistent evidence keys are content-derived and carry the full SHA-256.
#: They are database identity for immutable observations, never something a
#: person types, so there is nothing to trade collision resistance for.


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
        """Persistent identity, derived from what the fact *is*.

        Deliberately not built from `id`. The local ordinal describes a
        position in one sheet, and positions move: if a tool is refused on a
        later run, the fact behind it slides up and inherits the vacated slot.
        A key built on that would silently name a different observation while
        looking unchanged, which is the worst possible failure for a store whose
        whole purpose is that evidence is immutable.

        Subject, tool, arguments, result digest and summary are all included, so
        two facts differ in the key exactly when they differ in substance.
        """
        payload = {
            "subject": self.subject,
            "tool": self.tool,
            "arguments": self.arguments,
            "result_digest": self.result_digest,
            "summary": self.summary,
        }
        rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return "E-" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()

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


#: Provider metadata copied into a frozen record, named field by field.
#:
#: An allowlist rather than a redaction pass, and the difference matters. A
#: redactor has to recognise a secret in order to remove one, so it protects
#: against the credential shapes somebody thought of and no others; the next
#: provider will return a header, an organisation id, or an account slug that no
#: rule was written for. Copying only named fields cannot leak a field nobody
#: named.
_METADATA_FIELDS: tuple[str, ...] = (
    "requested_model",
    "returned_model",
    "model_identity_confirmed",
    "response_id",
    "status",
    "incomplete_reason",
)

#: Usage counters, likewise named rather than copied. Every value is coerced to
#: an integer, so a provider returning an object where a number was expected
#: records nothing instead of an arbitrary repr of whatever it returned.
_USAGE_FIELDS: tuple[str, ...] = ("input_tokens", "output_tokens", "total_tokens")

#: Nested counters worth keeping. `reasoning_tokens` is the one that decides
#: whether an empty reply means the model had nothing to say or was still
#: thinking when the budget ran out.
_USAGE_DETAILS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("input_tokens_details", ("cached_tokens",)),
    ("output_tokens_details", ("reasoning_tokens",)),
)


def _int_or_none(value: Any) -> int | None:
    """An integer, or nothing. `bool` is not an integer here."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _usage_of(metadata: dict[str, Any]) -> dict[str, Any]:
    """The named usage counters, and only those."""
    raw = metadata.get("usage")
    if not isinstance(raw, dict):
        return {}
    usage: dict[str, Any] = {}
    for name in _USAGE_FIELDS:
        value = _int_or_none(raw.get(name))
        if value is not None:
            usage[name] = value
    for group, names in _USAGE_DETAILS:
        nested = raw.get(group)
        if not isinstance(nested, dict):
            continue
        kept = {name: _int_or_none(nested.get(name)) for name in names}
        kept = {name: value for name, value in kept.items() if value is not None}
        if kept:
            usage[group] = kept
    return usage


@dataclass(frozen=True)
class ModelCall:
    """What produced a reply, frozen alongside the reply itself.

    `Investigation` used to record two strings - a provider name and a model
    name - and the transport had already returned far more than that. Everything
    else was dropped before anything was written down, so a frozen transcript
    could not say which snapshot answered, under what output ceiling, whether
    the reply was cut off, or what the call cost. This record closes that gap and
    does nothing else.

    Deliberately free of wall-clock time, run identity, and environment. Two
    identical investigations must serialize identically, because a transcript is
    compared and re-scored; the things that are true of an occasion rather than
    of a call belong to the capture record, which is a separate artifact.

    `failure` carries the transport fault when there was one. A lost sample is
    still evidence: it records what was attempted and under what bound, which is
    the difference between a gap somebody can audit and a blank.
    """

    provider: str
    requested_model: str
    max_output_tokens: int
    returned_model: str = ""
    model_identity_confirmed: bool = False
    response_id: str = ""
    status: str = ""
    incomplete_reason: str = ""
    truncated: bool = False
    usage: dict[str, Any] = field(default_factory=dict)
    request_digest: str = ""
    reply_digest: str = ""
    failure: str = ""

    @property
    def reasoning_tokens(self) -> int | None:
        """Output-budget spend on reasoning, where the provider reported it."""
        details = self.usage.get("output_tokens_details")
        if not isinstance(details, dict):
            return None
        return _int_or_none(details.get("reasoning_tokens"))

    @classmethod
    def from_response(cls, response: Any, request: Any) -> ModelCall:
        """Build the record from a completed call.

        Typed loosely on purpose: `ModelResponse` and `ModelRequest` live in
        `provider.py`, which imports nothing from here, and a record of a call
        should not be the reason the two modules become circular.
        """
        metadata = response.metadata if isinstance(response.metadata, dict) else {}
        kept = {name: metadata.get(name) for name in _METADATA_FIELDS}
        return cls(
            provider=str(response.provider),
            requested_model=str(kept["requested_model"] or ""),
            max_output_tokens=int(request.max_output_tokens),
            returned_model=str(kept["returned_model"] or response.model or ""),
            model_identity_confirmed=bool(kept["model_identity_confirmed"]),
            response_id=str(kept["response_id"] or ""),
            status=str(kept["status"] or ""),
            incomplete_reason=str(kept["incomplete_reason"] or ""),
            truncated=bool(response.truncated),
            usage=_usage_of(metadata),
            request_digest=canonical_digest(request.as_dict()),
            reply_digest=canonical_digest(response.text),
        )

    @classmethod
    def from_failure(cls, provider_name: str, request: Any, failure: str) -> ModelCall:
        """Build the record for a call that did not return a usable reply."""
        return cls(
            provider=provider_name,
            requested_model="",
            max_output_tokens=int(request.max_output_tokens),
            request_digest=canonical_digest(request.as_dict()),
            failure=failure,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "requested_model": self.requested_model,
            "returned_model": self.returned_model,
            "model_identity_confirmed": self.model_identity_confirmed,
            "response_id": self.response_id,
            "status": self.status,
            "incomplete_reason": self.incomplete_reason,
            "truncated": self.truncated,
            "max_output_tokens": self.max_output_tokens,
            "usage": dict(self.usage),
            "reasoning_tokens": self.reasoning_tokens,
            "request_digest": self.request_digest,
            "reply_digest": self.reply_digest,
            "failure": self.failure,
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
    #: The whole record of the call, where one was made. `model_provider` and
    #: `model_name` stay for the readers that already use them; this is what
    #: they were always two thirds of.
    model_call: ModelCall | None = None
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
            "model_call": None if self.model_call is None else self.model_call.as_dict(),
            "failure": self.failure,
        }


@dataclass(frozen=True)
class InvestigationBudget:
    """Bounds on one investigation, so a run cannot grow without limit.

    `max_output_tokens` is the one bound here that can be set too *low*. The
    others cap how much the model is shown; this one caps what it may produce,
    and on a reasoning model that ceiling covers reasoning as well as visible
    output. Set it too tightly and the model spends the whole allowance
    thinking and returns nothing - a failure that looks like a broken provider
    and is not one.

    That is a reason to make the ceiling settable, not a reason to raise it
    here. The default stays where it has always been; an experiment that needs
    more room states how much it needs, and that number becomes part of its
    provenance rather than something it inherited without noticing.
    """

    #: Unchanged. A caller that needs more room passes it explicitly, so the
    #: value used is recorded by whoever chose it.
    max_output_tokens: int = 2048
    max_instructions: int = 64
    max_callers: int = 20
    max_callees: int = 20
    max_claims: int = 20
    max_citations_per_claim: int = 8
    decompile: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
