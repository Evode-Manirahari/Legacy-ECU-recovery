"""The agent-phase thresholds, and what passing them does not mean.

Four of these are gated at a perfect score. That is not an expectation of the
model - it is because they measure the machinery around it. A fabricated
citation reaching a surviving claim, or an unparsed reply counted as an answer,
is a failure of checking rather than of reasoning, and there is no acceptable
rate for it.

Classification is baselined and never gated. EVALS.md forbids inventing a
flattering threshold before seeing performance, and the measure implemented here
is a lexical proxy that would not deserve one even if the numbers looked good.
"""

from __future__ import annotations

from typing import Any

from ..models import GateCheck
from .models import AgentMetrics

GATE_TARGETS: tuple[tuple[str, str, float], ...] = (
    ("evidence_reference_validity", "==", 100.0),
    ("schema_compliance", "==", 100.0),
    ("unsupported_factual_claims", "<=", 5.0),
    ("tool_hallucinations", "==", 0.0),
    ("critical_unsupported_claims", "==", 0.0),
)


class AgentGateCheck(GateCheck):
    """A gate check that also understands `<=`, which the static gate never needed."""

    @property
    def passed(self) -> bool:
        value = self.observed_value
        if value is None:
            return False
        if self.comparison == "<=":
            return value <= self.threshold
        return super().passed

    def render_target(self) -> str:
        suffix = "" if self.observed_count is not None else "%"
        return f"{self.comparison} {self.threshold:g}{suffix}"


def check_gate(metrics: AgentMetrics) -> tuple[AgentGateCheck, ...]:
    ratios: dict[str, Any] = {
        "evidence_reference_validity": metrics.evidence_reference_validity,
        "schema_compliance": metrics.schema_compliance,
        "unsupported_factual_claims": metrics.unsupported_factual_claims,
    }
    counts = {
        "tool_hallucinations": metrics.tool_hallucinations,
        "critical_unsupported_claims": metrics.critical_unsupported_claims,
    }
    checks: list[AgentGateCheck] = []
    for metric, comparison, threshold in GATE_TARGETS:
        if metric in counts:
            checks.append(
                AgentGateCheck(
                    metric=metric,
                    comparison=comparison,
                    threshold=threshold,
                    observed_count=counts[metric],
                )
            )
            continue
        checks.append(
            AgentGateCheck(
                metric=metric,
                comparison=comparison,
                threshold=threshold,
                observed=ratios[metric],
            )
        )
    return tuple(checks)
