# NODE: AGENT-001

**Title:** Bounded investigator agent
**Depends on:** `GATE-STATIC-MVP`
**Verification:** commands
**Retry budget:** 2

## Goal

Turn deterministic tool output into evidence-backed explanations of what a
function does.

This is the first node permitted to use a model. The division the project rests
on does not change:

> tools derive facts; AI interprets facts; experiments challenge
> interpretations; verification determines correctness.

The model interprets. It does not retrieve, and it does not decide what is true.

## Ownership

Allowed: `src/ecu_recovery/agent/**`, `tests/agent/**`.

Forbidden: `src/ecu_recovery/tools/**`, `src/ecu_recovery/analysis/**`,
`src/ecu_recovery/evidence/**`, `src/ecu_recovery/evaluation/**`,
`samples/**`, `graph/**`. If a tool is missing something the agent needs, report
it as an interface finding; do not reach around the tool layer.

## Scope

Operate on the **synthetic corpus** through the **existing `ToolRegistry`**.

Both halves are deliberate. The corpus is already verified with hidden ground
truth, and the tool layer is already measured. Introducing a model against a new
architecture at the same time would make every failure ambiguous — a wrong
answer could be the model or the unfamiliar target, with no way to tell which.
MPC5xx data work is a separate, later step.

## Required properties

1. **Every factual claim cites tool output.** A citation names the tool, the
   arguments, and the address or function id it came from, and it must resolve:
   re-running the cited call must produce the cited fact.

2. **The agent reaches the system only through `ToolRegistry.call`.** No direct
   analysis session, no Ghidra, no filesystem, no shell, no network. The bounded
   surface is the whole interface.

3. **A tool error is never a fact.** A failed call is an absence of information.
   It must not become an assertion, and the agent must not retry it into a
   different answer.

4. **Unknowns stay unknown.** A claim the tools cannot support is marked
   inferred or unknown, never stated flatly. Fabricated evidence is a critical
   failure, not a style problem.

5. **Output is structured and persistable.** Explanations map onto the existing
   `Hypothesis` / `Evidence` / `Relationship` model from `EVIDENCE-001` without
   changing it.

6. **Deterministic parts stay deterministic.** Prompt construction, tool
   dispatch, response parsing, and evidence assembly are testable without a
   model. Model calls are isolated behind an interface a test can substitute.

7. **The suite runs without an API key.** Model-backed tests skip with a stated
   reason, exactly as the Ghidra-marked tests do.

## Deliverables

The agent, its prompt construction, its evidence assembly, and tests covering
citation resolution, refusal handling, unknown marking, and the model-free path.

## Acceptance

```bash
uv run pytest
```

All accumulated regressions must keep passing.

## Exclusions

Do not measure the agent's accuracy here — that is `EVAL-AGENT-001`, and a node
must not grade itself. No emulation, no symbolic execution, no real firmware, no
flashing, no vehicle control.

## Stop

Return the structured handoff and stop.
