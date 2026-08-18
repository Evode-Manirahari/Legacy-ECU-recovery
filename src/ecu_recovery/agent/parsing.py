"""Parse a model reply strictly.

Strictly, because the alternative is guessing. A reply that does not match the
requested shape is a parse failure with a stated reason, never a best-effort
reconstruction: a salvaged claim is one whose provenance nobody can describe.

The one accommodation made is stripping a Markdown code fence, because models
add them constantly and doing so changes no meaning.
"""

from __future__ import annotations

import json
from typing import Any

from .models import Citation, Claim, InvestigationBudget, SupportLevel

CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {"type": "object"},
        }
    },
    "required": ["claims"],
}


class ReplyFormatError(ValueError):
    """The model's reply did not match the requested shape."""


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 2:
        return stripped
    body = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
    return "\n".join(body).strip()


def parse_claims(
    text: str, subject: str, budget: InvestigationBudget | None = None
) -> tuple[Claim, ...]:
    """Convert a reply into claims, or refuse with a reason."""
    budget = budget or InvestigationBudget()
    try:
        payload: Any = json.loads(_strip_fence(text))
    except json.JSONDecodeError as error:
        raise ReplyFormatError(f"reply is not JSON: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise ReplyFormatError("reply must be an object with a 'claims' array")

    claims: list[Claim] = []
    for index, raw in enumerate(payload["claims"]):
        if len(claims) >= budget.max_claims:
            break
        if not isinstance(raw, dict):
            raise ReplyFormatError(f"claim {index} is not an object")
        statement = str(raw.get("statement", "")).strip()
        if not statement:
            raise ReplyFormatError(f"claim {index} has no statement")
        support_text = str(raw.get("support", "")).strip().lower()
        try:
            support = SupportLevel(support_text)
        except ValueError as error:
            raise ReplyFormatError(
                f"claim {index} has support {support_text!r}; expected one of "
                f"{[item.value for item in SupportLevel]}"
            ) from error
        raw_confidence = raw.get("confidence", 0.0)
        if isinstance(raw_confidence, bool) or not isinstance(raw_confidence, (int, float)):
            raise ReplyFormatError(f"claim {index} has a non-numeric confidence")
        confidence = float(raw_confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ReplyFormatError(f"claim {index} has confidence {confidence} outside 0..1")
        raw_citations = raw.get("citations", [])
        if not isinstance(raw_citations, list):
            raise ReplyFormatError(f"claim {index} has a non-list citations field")
        citations = tuple(
            Citation(fact_id=str(item)) for item in raw_citations[: budget.max_citations_per_claim]
        )
        # An unknown that cites facts and carries confidence is not an unknown.
        if support is SupportLevel.UNKNOWN:
            citations = ()
            confidence = 0.0
        claims.append(
            Claim(
                subject=subject,
                statement=statement,
                support=support,
                citations=citations,
                confidence=confidence,
            )
        )
    return tuple(claims)
