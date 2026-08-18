"""Turn a fact sheet into a request, deterministically.

Rendering is pure and testable: the same sheet always produces the same bytes,
so a change in a transcript means the facts changed or the instructions changed,
never that the renderer drifted.

The instructions are strict about two things, because they are the two failure
modes that matter. Every claim must cite a fact id from the sheet, and a claim
the facts do not support must be marked `unknown` rather than softened into a
confident-sounding guess.
"""

from __future__ import annotations

import json

from .models import FactSheet, InvestigationBudget
from .provider import ModelRequest

INSTRUCTIONS = """\
You are analysing one function from a stripped firmware binary.

You are given facts that were already gathered by deterministic tools. You have
no tools of your own and cannot look anything up. Interpret only what is below.

Answer with a single JSON object and nothing else:

{"claims": [
  {"statement": "...", "support": "observed|inferred|unknown",
   "confidence": 0.0, "citations": ["F000", "F002"]}
]}

Rules:
- "observed" means a listed fact states it directly. Cite the fact ids.
- "inferred" means you reasoned from listed facts. Cite the facts you reasoned
  from.
- "unknown" means the facts do not settle it. Use it freely; say what would
  settle it in the statement. Cite nothing.
- Every citation must be a fact id that appears below. Never invent one, and
  never cite a tool call that is not listed.
- confidence is between 0.0 and 1.0 and must be 0.0 for "unknown".
- Do not describe what the function is named. In a stripped binary the name is
  generated and means nothing.
"""


def render_fact_sheet(sheet: FactSheet) -> str:
    lines = [f"Subject: {sheet.subject}", "", "Facts:"]
    lines.extend(f"  {fact.id}  [{fact.tool}] {fact.summary}" for fact in sheet.facts)
    if not sheet.facts:
        lines.append("  (none gathered)")
    if sheet.refusals:
        lines += [
            "",
            "Tool calls that did not return (these are absences of information,",
            "not findings, and must not be cited):",
        ]
        lines.extend(f"  [{tool}] {error}" for tool, error in sheet.refusals)
    return "\n".join(lines)


def build_request(sheet: FactSheet, budget: InvestigationBudget | None = None) -> ModelRequest:
    budget = budget or InvestigationBudget()
    return ModelRequest(
        instructions=INSTRUCTIONS.rstrip(),
        context=render_fact_sheet(sheet),
        max_output_tokens=2048,
    )


def expected_schema() -> str:
    """The reply shape, as JSON, for tests and for documentation."""
    return json.dumps(
        {
            "claims": [
                {
                    "statement": "str",
                    "support": "observed|inferred|unknown",
                    "confidence": "float 0..1",
                    "citations": ["fact id"],
                }
            ]
        },
        indent=2,
    )
