# NODE: DATA-001

**Title:** Synthetic firmware laboratory
**Depends on:** `GRAPH-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Create controlled binary fixtures with hidden ground truth.

## Ownership

Allowed: `samples/**`, `scripts/**`, `tests/**`, `docs/synthetic-lab.md`.

Forbidden: `src/**`, `graph/**`, `prompts/**`.

## Required fixture categories

1. temperature threshold controller;
2. RPM-like calculation;
3. one-dimensional lookup table;
4. two-dimensional lookup table;
5. state machine;
6. multi-function call graph;
7. integer/bit-mask manipulation;
8. timer-like counter logic.

## For every fixture preserve

Source, compiler identity, compiler flags, target architecture, unstripped
build, stripped build, expected functions, expected constants, expected
relationships, and expected behavior.

The analysis agent must never receive source or ground truth during evaluation.

## Scope, ruled 2026-08-17

This node does **not** solve the x86-64 Mach-O portability question. Do this
and only this:

- verify the existing fixture categories;
- add the missing integer/bit-mask fixture;
- add the missing timer-like counter fixture;
- preserve machine-readable ground truth;
- preserve reproducible builds;
- pass the node's tests.

Keep the current x86-64 Mach-O constraint documented as a known limitation —
including that CI cannot execute those fixtures on Linux, so they skip there.

Do not redesign the fixture laboratory around a new processor architecture.
`RESEARCH-001` will inform the eventual target-architecture decision, and
rebuilding the laboratory before that recommendation exists would mean choosing
twice.

## Candidate implementation to audit

Six of the eight categories exist from pre-graph work; categories 7 and 8 are
missing. Treat the existing fixtures as candidate implementation: audit them
against the contract and implement only what is missing or incorrect.

## Acceptance

```bash
uv run pytest
```

Plus fixture-specific tests. All existing regressions must keep passing.

## Exclusions

Do not add AI or Ghidra functionality.

## Stop

Return the structured handoff and stop.
