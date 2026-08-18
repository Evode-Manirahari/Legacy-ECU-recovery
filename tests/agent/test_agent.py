"""The investigator's machinery, proved without a model.

Every test here runs with a scripted double, which is the point rather than a
compromise: gathering, rendering, parsing, citation checking, and demotion are
deterministic, and if they needed a live model to test then the deterministic
claim would be false.

What is *not* tested here is whether the agent's interpretations are any good.
That is EVAL-AGENT-001's job, and a node that grades itself is not evidence.
"""

from __future__ import annotations

import json

import pytest
from agent_support import SUBJECT, ScriptedProvider, fake_context, unavailable_provider

from ecu_recovery.agent import (
    Citation,
    InvestigationBudget,
    ReplyFormatError,
    SupportLevel,
    UnconfiguredProvider,
    build_request,
    check_citation,
    gather_facts,
    investigate,
    parse_claims,
    render_fact_sheet,
    to_evidence,
    to_hypotheses,
)
from ecu_recovery.agent.provider import ModelProvider, ModelUnavailableError
from ecu_recovery.models import Certainty


def reply(*claims: dict[str, object]) -> str:
    return json.dumps({"claims": list(claims)})


# --- the model boundary ---


def test_the_provider_interface_is_one_method_and_vendor_free() -> None:
    """A provider SDK would have been a dependency this node is not allowed to add."""
    assert isinstance(ScriptedProvider(), ModelProvider)
    assert isinstance(UnconfiguredProvider(), ModelProvider)


def test_no_provider_sdk_is_imported_anywhere_in_the_agent() -> None:
    import pathlib

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in pathlib.Path("src/ecu_recovery/agent").glob("*.py")
    )
    for token in ("openai", "anthropic", "httpx", "requests", "urllib.request", "socket"):
        assert token not in source, f"{token} would make the model boundary vendor-specific"


def test_an_unconfigured_provider_refuses_clearly_instead_of_pretending() -> None:
    with pytest.raises(ModelUnavailableError, match="no model provider is configured"):
        UnconfiguredProvider().complete(build_request(gather_facts(fake_context(), SUBJECT)))


# --- gathering: only through the tool layer ---


def test_facts_are_gathered_only_through_the_tool_registry() -> None:
    calls: list[str] = []

    class SpyRegistry:
        def call(self, name, context, arguments=None):  # type: ignore[no-untyped-def]
            calls.append(name)
            from ecu_recovery.tools import REGISTRY

            return REGISTRY.call(name, context, arguments)

    gather_facts(fake_context(), SUBJECT, registry=SpyRegistry())  # type: ignore[arg-type]

    assert calls
    assert set(calls) <= {
        "binary_summary",
        "inspect_function",
        "get_callers",
        "get_callees",
        "decompile_function",
    }


def test_gathering_is_deterministic() -> None:
    first = gather_facts(fake_context(), SUBJECT)
    second = gather_facts(fake_context(), SUBJECT)

    assert first.as_dict() == second.as_dict()
    assert [item.id for item in first.facts] == [f"F{i:03d}" for i in range(len(first.facts))]


def test_a_refused_tool_call_becomes_a_refusal_not_a_fact() -> None:
    """The failure mode: an error object read as a finding."""
    sheet = gather_facts(fake_context(failing_tool="get_callers"), SUBJECT)

    assert ("get_callers", "analysis_failed") in sheet.refusals
    assert not any(fact.tool == "get_callers" for fact in sheet.facts)


def test_a_failed_decompilation_is_recorded_as_an_absence() -> None:
    sheet = gather_facts(fake_context(decompiles=False), SUBJECT)

    assert ("decompile_function", "decompilation_failed") in sheet.refusals
    assert not any(fact.tool == "decompile_function" for fact in sheet.facts)


# --- prompting ---


def test_the_rendered_sheet_is_deterministic_and_lists_every_fact() -> None:
    sheet = gather_facts(fake_context(), SUBJECT)

    rendered = render_fact_sheet(sheet)

    assert rendered == render_fact_sheet(sheet)
    for fact in sheet.facts:
        assert fact.id in rendered


def test_refusals_are_shown_to_the_model_as_absences() -> None:
    sheet = gather_facts(fake_context(failing_tool="get_callers"), SUBJECT)

    rendered = render_fact_sheet(sheet)

    assert "absences of information" in rendered
    assert "get_callers" in rendered


def test_the_instructions_forbid_inventing_citations() -> None:
    request = build_request(gather_facts(fake_context(), SUBJECT))

    assert "Never invent one" in request.instructions
    assert '"unknown"' in request.instructions


# --- parsing, strictly ---


def test_a_well_formed_reply_parses() -> None:
    claims = parse_claims(
        reply(
            {
                "statement": "adds one",
                "support": "observed",
                "confidence": 0.9,
                "citations": ["F001"],
            }
        ),
        SUBJECT,
    )

    assert len(claims) == 1
    assert claims[0].support is SupportLevel.OBSERVED
    assert claims[0].citations == (Citation("F001"),)


def test_a_fenced_reply_still_parses() -> None:
    fenced = (
        "```json\n" + reply({"statement": "x", "support": "unknown", "confidence": 0}) + "\n```"
    )

    assert len(parse_claims(fenced, SUBJECT)) == 1


@pytest.mark.parametrize(
    "text",
    [
        "not json at all",
        '{"no_claims_key": []}',
        '{"claims": [{"support": "observed"}]}',
        '{"claims": [{"statement": "x", "support": "maybe"}]}',
        '{"claims": [{"statement": "x", "support": "observed", "confidence": 5}]}',
        '{"claims": [{"statement": "x", "support": "observed", "confidence": true}]}',
        '{"claims": [{"statement": "x", "support": "observed", "citations": "F001"}]}',
    ],
)
def test_a_malformed_reply_is_refused_rather_than_salvaged(text: str) -> None:
    """Guessing at a broken reply produces a claim whose provenance is fiction."""
    with pytest.raises(ReplyFormatError):
        parse_claims(text, SUBJECT)


def test_an_unknown_claim_cannot_smuggle_confidence_or_citations() -> None:
    claims = parse_claims(
        reply(
            {
                "statement": "cannot tell",
                "support": "unknown",
                "confidence": 0.9,
                "citations": ["F001"],
            }
        ),
        SUBJECT,
    )

    assert claims[0].confidence == 0.0
    assert claims[0].citations == ()


def test_claim_count_is_bounded() -> None:
    many = [{"statement": f"c{i}", "support": "unknown", "confidence": 0} for i in range(50)]

    claims = parse_claims(reply(*many), SUBJECT, InvestigationBudget(max_claims=5))

    assert len(claims) == 5


# --- citation checking ---


def test_a_citation_to_a_gathered_fact_resolves_by_re_running_it() -> None:
    context = fake_context()
    sheet = gather_facts(context, SUBJECT)

    check = check_citation(Citation(sheet.facts[0].id), sheet, context)

    assert check.resolved is True
    assert check.fabricated is False


def test_a_citation_to_a_fact_never_gathered_is_fabrication() -> None:
    """Not an error: the agent said a tool produced something it never produced."""
    context = fake_context()
    sheet = gather_facts(context, SUBJECT)

    check = check_citation(Citation("F999"), sheet, context)

    assert check.resolved is False
    assert check.fabricated is True
    assert "never made" in check.reason


# --- the whole path ---


def test_an_investigation_keeps_supported_claims() -> None:
    context = fake_context()
    provider = ScriptedProvider(
        reply=reply(
            {
                "statement": "increments its argument",
                "support": "observed",
                "confidence": 0.8,
                "citations": ["F001"],
            }
        )
    )

    result = investigate(context, SUBJECT, provider)

    assert result.failure is None
    assert len(result.claims) == 1
    assert result.claims[0].support is SupportLevel.OBSERVED
    assert result.demotions == ()
    assert result.fabricated_citations == ()


def test_an_unsupported_claim_is_demoted_and_the_demotion_recorded() -> None:
    """An overreach that vanished silently would be invisible to evaluation."""
    provider = ScriptedProvider(
        reply=reply(
            {
                "statement": "controls the fuel pump",
                "support": "observed",
                "confidence": 0.95,
                "citations": ["F999"],
            }
        )
    )

    result = investigate(fake_context(), SUBJECT, provider)

    assert result.claims[0].support is SupportLevel.UNKNOWN
    assert result.claims[0].confidence == 0.0
    assert result.demotions == ("controls the fuel pump",)
    assert len(result.fabricated_citations) == 1


def test_an_unknown_claim_needs_no_citation_and_survives() -> None:
    provider = ScriptedProvider(
        reply=reply(
            {
                "statement": "purpose is not determinable from these facts",
                "support": "unknown",
                "confidence": 0,
            }
        )
    )

    result = investigate(fake_context(), SUBJECT, provider)

    assert result.claims[0].support is SupportLevel.UNKNOWN
    assert result.demotions == ()


def test_a_missing_provider_is_a_recorded_outcome_not_a_crash() -> None:
    result = investigate(fake_context(), SUBJECT, unavailable_provider())

    assert result.failure is not None
    assert "model unavailable" in result.failure
    assert result.claims == ()
    # The deterministic half still ran and is still worth having.
    assert result.fact_sheet.facts


def test_a_provider_that_explodes_does_not_take_the_run_with_it() -> None:
    result = investigate(fake_context(), SUBJECT, ScriptedProvider(raises=RuntimeError("boom")))

    assert result.failure is not None
    assert "RuntimeError" in result.failure


def test_an_unusable_reply_is_a_recorded_outcome() -> None:
    result = investigate(fake_context(), SUBJECT, ScriptedProvider(reply="¯\\_(ツ)_/¯"))

    assert result.failure is not None
    assert "unusable reply" in result.failure
    assert result.claims == ()


def test_the_model_is_never_handed_a_tool() -> None:
    """It gets facts, not the ability to fetch them. Retrieval stays deterministic."""
    provider = ScriptedProvider()

    investigate(fake_context(), SUBJECT, provider)

    request = provider.requests[0]
    assert "Facts:" in request.context
    assert "no tools of your own" in request.instructions


def test_an_investigation_serializes() -> None:
    provider = ScriptedProvider(
        reply=reply(
            {
                "statement": "adds one",
                "support": "inferred",
                "confidence": 0.6,
                "citations": ["F001"],
            }
        )
    )

    result = investigate(fake_context(), SUBJECT, provider)

    assert json.loads(json.dumps(result.as_dict()))["subject"] == SUBJECT


# --- mapping onto the existing evidence model ---


def test_gathered_facts_become_mechanically_observed_evidence() -> None:
    sheet = gather_facts(fake_context(), SUBJECT)

    evidence = to_evidence(sheet)

    assert evidence
    assert all(item.mechanically_observed for item in evidence)
    assert all(item.source.startswith("tools:") for item in evidence)


def test_nothing_the_model_said_becomes_evidence() -> None:
    """Evidence is what a tool observed. A claim is an interpretation of it."""
    provider = ScriptedProvider(
        reply=reply(
            {
                "statement": "invented",
                "support": "observed",
                "confidence": 1.0,
                "citations": ["F001"],
            }
        )
    )
    result = investigate(fake_context(), SUBJECT, provider)

    summaries = " ".join(item.summary for item in to_evidence(result.fact_sheet))

    assert "invented" not in summaries


def test_claims_map_onto_hypotheses_the_evidence_model_accepts() -> None:
    provider = ScriptedProvider(
        reply=reply(
            {
                "statement": "adds one",
                "support": "observed",
                "confidence": 0.8,
                "citations": ["F001"],
            },
            {
                "statement": "may be a counter",
                "support": "inferred",
                "confidence": 0.4,
                "citations": ["F002"],
            },
            {"statement": "cannot tell what calls it", "support": "unknown", "confidence": 0},
        )
    )
    result = investigate(fake_context(), SUBJECT, provider)

    paired = to_hypotheses(result)

    assert [h.certainty for h, _ in paired] == [
        Certainty.KNOWN,
        Certainty.INFERRED,
        Certainty.UNKNOWN,
    ]
    # KNOWN claims must carry full confidence or the evidence model rejects them.
    assert paired[0][0].confidence == 1.0
    assert paired[0][1] == ("E-F001",)
    assert paired[2][1] == ()
