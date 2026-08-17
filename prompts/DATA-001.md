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

## Candidate implementation to audit

Six of the eight categories exist from pre-graph work. Categories 7 and 8 are
missing. Some behavior fixtures are tied to x86-64 macOS/Mach-O, which also
means CI cannot execute them on Linux. This node owns the decision to keep,
extend, or make the fixture target more portable.

Treat existing fixtures as candidate implementation. Audit them against all
eight categories and implement only what is missing or incorrect.

## Acceptance

```bash
uv run pytest
```

Plus fixture-specific tests. All existing regressions must keep passing.

## Exclusions

Do not add AI or Ghidra functionality.

## Stop

Return the structured handoff and stop.
