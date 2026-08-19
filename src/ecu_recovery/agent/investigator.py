"""Gather, interpret, then check what was said against what was gathered.

The order is the argument. Facts are collected deterministically before any
model sees anything, the model is given only those facts, and every claim it
makes is checked back against them afterwards. A wrong answer is therefore
attributable: retrieval already happened and is reproducible, so what is left is
interpretation.

Checking is not a formality, and three details decide whether it means anything.

Replay compares the **result**, not the exit status. A tool can succeed and
return something else; a citation that only proves the call still works proves
nothing about the claim resting on it.

**Every** citation on a factual claim must survive. Requiring only one to hold
would let a claim carrying one real citation and one fabricated one stand as
observed, which is exactly the shape a plausible-sounding wrong answer takes.

A model-authored claim never becomes mechanically known. The model labelling its
own statement "observed" is not a measurement, and `Certainty.KNOWN` is reserved
for what a deterministic tool established. The label is kept in the transcript
because EVAL-AGENT-001 needs to score whether the model classified itself
correctly; it just does not get to promote itself in the evidence store.

Demotion is recorded rather than applied silently, because "the agent overreached
and was caught" and "the agent was careful" must not produce the same
transcript.
"""

from __future__ import annotations

from ..models import Certainty, Evidence, EvidenceKind, Hypothesis
from ..tools import REGISTRY, ToolContext, ToolRegistry
from .gathering import gather_facts
from .models import (
    Citation,
    CitationCheck,
    Claim,
    FactSheet,
    Investigation,
    InvestigationBudget,
    SupportLevel,
    canonical_digest,
)
from .parsing import ReplyFormatError, parse_claims
from .prompting import build_request
from .provider import ModelProvider, ModelUnavailableError, UnconfiguredProvider

#: Claims at this level or stronger must survive citation checking.
_REQUIRES_SUPPORT = (SupportLevel.OBSERVED, SupportLevel.INFERRED)

#: A model-authored claim is an interpretation whatever the model calls it, so
#: OBSERVED and INFERRED both persist as INFERRED. `Certainty.KNOWN` belongs to
#: what a tool established, and tool facts already become mechanically observed
#: Evidence. Promoting a claim to KNOWN would let the model's self-assessment
#: overwrite that distinction. If a deterministic semantic validator ever exists,
#: it - not the model - is what would justify changing this.
_CERTAINTY_FOR = {
    SupportLevel.OBSERVED: Certainty.INFERRED,
    SupportLevel.INFERRED: Certainty.INFERRED,
    SupportLevel.UNKNOWN: Certainty.UNKNOWN,
}


def check_citation(
    citation: Citation,
    sheet: FactSheet,
    context: ToolContext,
    registry: ToolRegistry = REGISTRY,
) -> CitationCheck:
    """Resolve one citation: gathered, re-runnable, and still saying the same thing.

    Three ways to fail, and they are not the same failure. An id that was never
    gathered means the agent cited a call it never made - fabrication. A call
    that no longer succeeds means the fact is no longer obtainable. A call that
    succeeds with a different result means the fact has moved, and a citation
    that resolved on exit status alone would have hidden that.
    """
    fact = sheet.by_id(citation.fact_id)
    if fact is None:
        return CitationCheck(
            citation=citation,
            resolved=False,
            fabricated=True,
            reason=f"no fact {citation.fact_id!r} was gathered; the call was never made",
        )
    replay = registry.call(fact.tool, context, fact.arguments)
    if not replay.ok or replay.data is None:
        error = replay.error
        return CitationCheck(
            citation=citation,
            resolved=False,
            reason=(
                f"re-running {fact.tool} did not succeed: "
                f"{'unknown error' if error is None else error.code}"
            ),
        )
    replayed = canonical_digest(replay.data)
    if replayed != fact.result_digest:
        return CitationCheck(
            citation=citation,
            resolved=False,
            reason=(
                f"{fact.tool} re-ran but returned different data: recorded "
                f"{fact.result_digest}, replayed {replayed}"
            ),
        )
    return CitationCheck(
        citation=citation,
        resolved=True,
        reason=f"{fact.tool} re-ran and reproduced fact {fact.id} ({fact.result_digest})",
    )


def investigate(
    context: ToolContext,
    subject: str,
    provider: ModelProvider | None = None,
    budget: InvestigationBudget | None = None,
    registry: ToolRegistry = REGISTRY,
) -> Investigation:
    """Investigate one function. Never raises; failure is a recorded outcome."""
    budget = budget or InvestigationBudget()
    provider = provider or UnconfiguredProvider()
    sheet = gather_facts(context, subject, budget, registry)

    try:
        response = provider.complete(build_request(sheet, budget))
    except ModelUnavailableError as error:
        return Investigation(
            subject=subject,
            fact_sheet=sheet,
            model_provider=getattr(provider, "name", "unknown"),
            failure=f"model unavailable: {error}",
        )
    except Exception as error:  # noqa: BLE001 - a provider fault must not crash a run
        return Investigation(
            subject=subject,
            fact_sheet=sheet,
            model_provider=getattr(provider, "name", "unknown"),
            failure=f"provider raised {type(error).__name__}: {error}",
        )

    try:
        claims = parse_claims(response.text, subject, budget)
    except ReplyFormatError as error:
        return Investigation(
            subject=subject,
            fact_sheet=sheet,
            model_provider=response.provider,
            model_name=response.model,
            failure=f"unusable reply: {error}",
        )

    checks: list[CitationCheck] = []
    kept: list[Claim] = []
    demotions: list[str] = []
    for claim in claims:
        claim_checks = [
            check_citation(citation, sheet, context, registry) for citation in claim.citations
        ]
        checks.extend(claim_checks)
        # Every citation must hold, not merely one of them. A claim carrying a
        # real citation beside a fabricated one is the shape a confident wrong
        # answer takes, and `any` would wave it through. An uncited factual
        # claim is unsupported by definition.
        unsupported = claim.support in _REQUIRES_SUPPORT and (
            not claim_checks or not all(item.resolved for item in claim_checks)
        )
        if unsupported:
            # Kept, not dropped: an overreach that vanishes is invisible to the
            # evaluation that is supposed to count it.
            demotions.append(claim.statement)
            kept.append(
                Claim(
                    subject=claim.subject,
                    statement=claim.statement,
                    support=SupportLevel.UNKNOWN,
                    citations=(),
                    confidence=0.0,
                )
            )
            continue
        kept.append(claim)

    return Investigation(
        subject=subject,
        fact_sheet=sheet,
        claims=tuple(kept),
        checks=tuple(checks),
        demotions=tuple(demotions),
        model_provider=response.provider,
        model_name=response.model,
    )


def to_evidence(sheet: FactSheet) -> tuple[Evidence, ...]:
    """Map gathered facts onto the existing evidence model.

    `mechanically_observed` is True for every one of these: they came from a
    deterministic tool and a rerun reproduces them. Nothing the model said is
    evidence, which is the distinction EVIDENCE-001 exists to hold.
    """
    return tuple(
        Evidence(
            key=fact.evidence_key,
            kind=EvidenceKind.STATIC_PROPERTY,
            summary=fact.summary[:400],
            source=f"tools:{fact.tool}",
            mechanically_observed=True,
            detail=str(fact.arguments),
        )
        for fact in sheet.facts
    )


def to_hypotheses(investigation: Investigation) -> tuple[tuple[Hypothesis, tuple[str, ...]], ...]:
    """Map claims onto hypotheses, paired with the evidence keys they cite.

    Evidence keys come from the `Fact` itself, the same place `to_evidence` gets
    them, so a hypothesis can never reference a key that was not generated. A
    citation whose fact is absent is dropped rather than emitted as a dangling
    reference - it cannot occur on a surviving factual claim, because such a
    claim was demoted, but persistence should not depend on that argument
    holding somewhere else.
    """
    sheet = investigation.fact_sheet
    paired: list[tuple[Hypothesis, tuple[str, ...]]] = []
    for claim in investigation.claims:
        certainty = _CERTAINTY_FOR[claim.support]
        keys: list[str] = []
        for citation in claim.citations:
            fact = sheet.by_id(citation.fact_id)
            if fact is not None:
                keys.append(fact.evidence_key)
        paired.append(
            (
                Hypothesis(
                    subject=claim.subject,
                    claim=claim.statement,
                    certainty=certainty,
                    confidence=claim.confidence,
                ),
                tuple(keys),
            )
        )
    return tuple(paired)
