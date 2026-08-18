"""Gather, interpret, then check what was said against what was gathered.

The order is the argument. Facts are collected deterministically before any
model sees anything, the model is given only those facts, and every claim it
makes is checked back against them afterwards. A wrong answer is therefore
attributable: retrieval already happened and is reproducible, so what is left is
interpretation.

Checking is not a formality. A citation naming a fact id that was never gathered
is recorded as **fabricated** - the agent claiming a tool said something it
never said - and any claim resting on citations that do not survive is demoted
to `unknown` rather than being quietly kept. Demotion is recorded too, because
"the agent overreached and was caught" and "the agent was careful" should not
produce the same transcript.
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
)
from .parsing import ReplyFormatError, parse_claims
from .prompting import build_request
from .provider import ModelProvider, ModelUnavailableError, UnconfiguredProvider

#: Claims at this level or stronger must survive citation checking.
_REQUIRES_SUPPORT = (SupportLevel.OBSERVED, SupportLevel.INFERRED)

_CERTAINTY_FOR = {
    SupportLevel.OBSERVED: Certainty.KNOWN,
    SupportLevel.INFERRED: Certainty.INFERRED,
    SupportLevel.UNKNOWN: Certainty.UNKNOWN,
}


def check_citation(
    citation: Citation,
    sheet: FactSheet,
    context: ToolContext,
    registry: ToolRegistry = REGISTRY,
) -> CitationCheck:
    """Resolve one citation, twice.

    First the fact id must belong to something actually gathered - a citation
    that fails here names a tool result the agent never obtained, which is
    fabrication rather than error. Then the recorded call is re-run and must
    still succeed, so a citation is a reproducible pointer rather than a claim
    about a moment that has passed.
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
    if not replay.ok:
        error = replay.error
        return CitationCheck(
            citation=citation,
            resolved=False,
            reason=(
                f"re-running {fact.tool} did not reproduce the fact: "
                f"{'unknown error' if error is None else error.code}"
            ),
        )
    return CitationCheck(
        citation=citation,
        resolved=True,
        reason=f"{fact.tool} re-ran and reproduced fact {fact.id}",
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
        unsupported = claim.support in _REQUIRES_SUPPORT and not any(
            item.resolved for item in claim_checks
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
            key=f"E-{fact.id}",
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

    A KNOWN claim must carry confidence 1.0 for the evidence model to accept it,
    and an OBSERVED claim is precisely one a tool stated directly, so the
    conversion is faithful rather than convenient.
    """
    paired: list[tuple[Hypothesis, tuple[str, ...]]] = []
    for claim in investigation.claims:
        certainty = _CERTAINTY_FOR[claim.support]
        confidence = 1.0 if certainty is Certainty.KNOWN else claim.confidence
        paired.append(
            (
                Hypothesis(
                    subject=claim.subject,
                    claim=claim.statement,
                    certainty=certainty,
                    confidence=confidence,
                ),
                tuple(f"E-{item.fact_id}" for item in claim.citations),
            )
        )
    return tuple(paired)
