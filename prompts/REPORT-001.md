# NODE: REPORT-001

**Title:** Faithful epistemic reporting
**Depends on:** `INTEGRATION-STATIC-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Make the human-facing engineering report represent epistemic state faithfully,
before the static MVP is certified.

`INTEGRATION-STATIC-001` found that it does not. `report.py` labels `Certainty`
as "Status" and never renders `HypothesisStatus`, the revision chain, or the
reason a belief changed. A `REJECTED` belief therefore renders identically to an
`UNTESTED` one — the report cannot say whether a belief survived testing, which
is the one thing this project exists to communicate.

## Ownership

Allowed: `src/ecu_recovery/report.py`, `tests/report/**`,
`tests/test_store_report.py`, `tests/integration/**`,
`artifacts/integration/**`.

The three paths beyond `report.py` and its own tests are all there for the same
reason: they pin the broken behaviour on purpose, and fixing it inverts them.

`tests/test_store_report.py` belongs to `EVIDENCE-001` and holds
`test_report_does_not_yet_render_status_or_history`, which asserts the report
says `- Status: **inferred**` and contains neither `supported` nor the change
reason. `EVIDENCE-001` wrote it that way because its contract forbade editing
`report.py`.

`tests/integration/**` and `artifacts/integration/**` belong to
`INTEGRATION-STATIC-001` and hold its finding that the gap exists, plus the
recorded report listing it. That node wrote its findings as auto-detected checks
precisely so a fix would retire them, and it does — the flow reports one finding
instead of three once this node lands. Only the assertion pinning the gap's
presence and the committed artifact need updating.

In all three cases: update what the fix invalidates and nothing else. Do not
weaken an unrelated assertion to make a suite go green.

Forbidden: `src/ecu_recovery/store.py`, the evidence schema and models,
`src/ecu_recovery/analysis/**`, `src/ecu_recovery/tools/**`,
`src/ecu_recovery/evaluation/**`, `tests/integration/**`,
`artifacts/**`, `samples/**`, `graph/**`.

## Required product outcomes

1. **`Certainty` and `HypothesisStatus` render as separate concepts.** The
   report must not label `Certainty` as "Status". Both must be visible and
   distinguishable. Use the project's existing enum and value formatting
   conventions rather than inventing new ones.

2. **The current hypothesis status is visible.** A reader must be able to tell
   `UNTESTED`, `SUPPORTED`, `WEAKENED`, `REJECTED`, and `CONFIRMED` apart. A
   `REJECTED` hypothesis must not render identically to an `UNTESTED` one.

3. **Belief revision information survives to the report.** For a hypothesis with
   more than one revision, render enough of the chain to show revision number,
   status, confidence, and `change_reason`. Render stored data only; do not
   invent interpretation or prose around it.

4. **Current-belief semantics are preserved.** The current revision stays
   clearly identifiable. Historical revisions must never read as
   simultaneously-held current beliefs.

5. **Evidence traceability is preserved.** Do not weaken or remove the evidence
   references the report already renders.

6. **Output stays deterministic.** No timestamps, absolute paths,
   environment-specific values, or unstable ordering.

7. **The safety notice and static-analysis framing are preserved.**

8. **No database or schema changes.** This node consumes the evidence model as
   `EVIDENCE-001` implemented it. Do not redesign it. If the stored data turns
   out to be insufficient for an outcome above, report that as an interface
   finding instead of changing the schema.

## Required tests

Under `tests/report/**`, proving:

- certainty and hypothesis status render as separate concepts;
- a `SUPPORTED` belief renders its status correctly;
- `REJECTED` and `UNTESTED` produce distinguishable reports;
- a two-revision hypothesis exposes its revision history;
- `change_reason` is rendered;
- the current belief remains clearly identifiable;
- existing evidence rendering is intact;
- rendering is deterministic for identical stored input.

## Acceptance

```bash
uv run pytest
```

All existing regressions must keep passing, including the accumulated
obligations of every previously passed node.

## Exclusions

Do not add an LLM. Do not change the evidence schema. Do not touch the analysis,
tool, evaluation, or integration layers. Do not start `GATE-STATIC-MVP`.

## Stop

Return the structured handoff and stop.
