# NODE: INTEGRATION-STATIC-001

**Title:** Static MVP integration
**Depends on:** `TOOLS-001`, `EVIDENCE-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Prove the static-analysis pieces actually cooperate end to end.

## Ownership

Allowed: `artifacts/integration/**`, `tests/integration/**`.

Forbidden: silently patching upstream modules. If an upstream contract must
change, report it explicitly instead of editing around it.

## Required flow

```text
synthetic stripped binary
  -> Ghidra analysis
  -> internal models
  -> bounded tool layer
  -> evidence persistence
  -> evaluation
```

No LLM is required in this node.

## Deliverables

```text
artifacts/integration/static-integration-report.md
```

Reporting successful steps, failed steps, performance, warnings, interface
mismatches, and open blockers.

## Acceptance

```bash
uv run pytest
```

Run every accumulated regression obligation from previously passed nodes, not
only this node's tests.

## Exclusions

Do not implement AI. Do not patch unrelated failures silently.

## Stop

Return the structured handoff and stop.
