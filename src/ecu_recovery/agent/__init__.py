"""The bounded investigator agent.

The first part of this system permitted to use a model, and the division it
preserves is the one the whole project rests on:

    tools derive facts; AI interprets facts; experiments challenge
    interpretations; verification determines correctness.

Facts are gathered deterministically through `ToolRegistry` before any model is
involved, and the model is handed those facts rather than tools. It cannot look
anything up, so retrieval stays reproducible and a wrong answer is attributable
to interpretation. Afterwards every claim is checked back against the sheet:
a citation naming a fact that was never gathered is recorded as fabricated, and
a claim whose citations do not survive is demoted to `unknown` with the demotion
recorded rather than hidden.

The model boundary is one method on a protocol. No provider SDK is imported and
no dependency was added; a real adapter is separately authorized work. Every
piece of machinery here is exercised with test doubles, which is why the suite
needs no API key.

This node does not measure whether the agent is any good. That is
`EVAL-AGENT-001`, because a node that grades itself is not evidence.
"""

from __future__ import annotations

from .gathering import gather_facts
from .investigator import check_citation, investigate, to_evidence, to_hypotheses
from .models import (
    Citation,
    CitationCheck,
    Claim,
    Fact,
    FactSheet,
    Investigation,
    InvestigationBudget,
    SupportLevel,
)
from .parsing import ReplyFormatError, parse_claims
from .prompting import INSTRUCTIONS, build_request, expected_schema, render_fact_sheet
from .provider import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelUnavailableError,
    UnconfiguredProvider,
)

__all__ = [
    "INSTRUCTIONS",
    "Citation",
    "CitationCheck",
    "Claim",
    "Fact",
    "FactSheet",
    "Investigation",
    "InvestigationBudget",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "ModelUnavailableError",
    "ReplyFormatError",
    "SupportLevel",
    "UnconfiguredProvider",
    "build_request",
    "check_citation",
    "expected_schema",
    "gather_facts",
    "investigate",
    "parse_claims",
    "render_fact_sheet",
    "to_evidence",
    "to_hypotheses",
]
