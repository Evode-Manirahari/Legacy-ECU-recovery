# NODE: GHIDRA-001

**Title:** Deterministic PyGhidra static analysis
**Depends on:** `DATA-001`, `REPO-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Deterministic static binary analysis through PyGhidra.

## Ownership

Allowed: `src/ecu_recovery/analysis/**`, `tests/analysis/**`.

Forbidden: `samples/**`, `src/ecu_recovery/evidence/**`, `graph/**`.

## Required operations

```text
analyze_binary
list_memory_regions
list_functions
get_function
decompile_function
get_callers
get_callees
get_cross_references
list_strings
search_constant
read_bytes
```

## Required models

`BinaryAnalysis`, `MemoryRegion`, `FunctionRecord`, `DecompilerResult`,
`CrossReference`.

Raw Ghidra/Java objects must not leak into the rest of the application.
Analysis results must serialize to JSON.

## CLI

```bash
ecu-recovery analyze <binary>
```

Output categories: binary metadata, memory map, function count, function
records, call relationships, and **analysis warnings**.

## Candidate implementation to audit

A PyGhidra adapter exists from pre-graph work with plain records, a bounded
session interface, and JSON export. Known gap: no analysis-warnings field.
Treat it as candidate implementation and verify it against this contract rather
than assuming it passes.

Ghidra-marked tests must skip with a stated reason when Ghidra is absent, so CI
stays green without it.

## Acceptance

```bash
uv run pytest
```

All existing regressions must keep passing.

## Exclusions

Do not add an LLM. Do not claim analysis correctness here; that is
`EVAL-STATIC-001`.

## Stop

Return the structured handoff and stop.
