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

from dataclasses import dataclass
from typing import Any

from ..models import GateCheck
from .models import AgentMetrics, Measurement

GATE_TARGETS: tuple[tuple[str, str, float], ...] = (
    ("evidence_reference_validity", "==", 100.0),
    ("schema_compliance", "==", 100.0),
    ("unsupported_factual_claims", "<=", 5.0),
    ("tool_hallucinations", "==", 0.0),
    ("critical_unsupported_claims", "==", 0.0),
)


@dataclass(frozen=True)
class AgentGateCheck(GateCheck):
    """A gate check understanding `<=`, and refusing to pass on an unmeasured metric."""

    unmeasured: bool = False
    unmeasured_reason: str = ""

    @property
    def passed(self) -> bool:
        # An unmeasured or non-quorum metric fails. It has not met the
        # threshold: nobody qualified has checked, and a gate that green-lights
        # on absence of evidence is not a gate.
        if self.unmeasured:
            return False
        value = self.observed_value
        if value is None:
            return False
        if self.comparison == "<=":
            return value <= self.threshold
        return super().passed

    def render_target(self) -> str:
        suffix = "" if self.observed_count is not None else "%"
        return f"{self.comparison} {self.threshold:g}{suffix}"

    def render_observed(self) -> str:
        if self.unmeasured:
            return "UNMEASURED"
        return super().render_observed()

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload["unmeasured"] = self.unmeasured
        payload["unmeasured_reason"] = self.unmeasured_reason
        return payload


def check_gate(metrics: AgentMetrics) -> tuple[AgentGateCheck, ...]:
    ratios: dict[str, Any] = {
        "evidence_reference_validity": metrics.evidence_reference_validity,
        "schema_compliance": metrics.schema_compliance,
        "unsupported_factual_claims": metrics.unsupported_factual_claims,
    }
    measurements: dict[str, Measurement] = {
        "critical_unsupported_claims": metrics.critical_unsupported_claims,
    }
    counts = {"tool_hallucinations": metrics.tool_hallucinations}
    checks: list[AgentGateCheck] = []
    for metric, comparison, threshold in GATE_TARGETS:
        if metric in measurements:
            measurement = measurements[metric]
            checks.append(
                AgentGateCheck(
                    metric=metric,
                    comparison=comparison,
                    threshold=threshold,
                    observed_count=measurement.count,
                    unmeasured=not measurement.gate_eligible,
                    unmeasured_reason=measurement.reason,
                )
            )
            continue
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
