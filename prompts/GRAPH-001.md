# NODE: GRAPH-001

**Title:** Development graph infrastructure
**Depends on:** `REPO-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Implement the minimum infrastructure required to represent, validate, and
inspect the development dependency DAG.

Do not build a full autonomous agent orchestrator.

## Ownership

Allowed: `ecu-project.graph.yaml`, `graph/**`, `prompts/**`, `artifacts/**`,
`tests/graph/**`, plus minimal status updates to `TODO.md` and
`ARCHITECTURE.md`.

Forbidden: `src/**`, `samples/**`, `scripts/**`, `pyproject.toml`.

## Required graph

```text
SPEC-001 -> REPO-001 -> GRAPH-001
GRAPH-001 -> DATA-001
GRAPH-001 -> RESEARCH-001
GRAPH-001 -> EVIDENCE-001
DATA-001 -> GHIDRA-001
GHIDRA-001 -> EVAL-STATIC-001
EVAL-STATIC-001 -> TOOLS-001
TOOLS-001 -> INTEGRATION-STATIC-001
EVIDENCE-001 -> INTEGRATION-STATIC-001
INTEGRATION-STATIC-001 -> GATE-STATIC-MVP
```

## Required node fields

`id`, `title`, `depends_on`, `status`, `worker`, `prompt`, `allowed_paths`,
`verification`, `retry_budget`.

## Valid states

`PENDING`, `READY`, `RUNNING`, `VERIFYING`, `PASSED`, `FAILED`, `BLOCKED`,
`NEEDS_HUMAN`, `UNVERIFIED-UNDER-GRAPH`.

Only `PASSED` satisfies a dependency edge.

## Required behaviour

List nodes, inspect dependencies, validate acyclicity, validate dependency
references, compute the READY frontier, list PASSED and BLOCKED nodes, and
compute what becomes READY after a node passes.

## The validator must reject

Cycles, duplicate node IDs, unknown dependencies, invalid state values, and
self-dependencies, with useful error messages.

## Acceptance

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Required tests: valid graph loads; cycle rejected; unknown dependency rejected;
self-dependency rejected; invalid status rejected; `SPEC-001` and `REPO-001`
read as passed; `GRAPH-001` in flight as appropriate; fan-out not READY before
`GRAPH-001` passes; `DATA-001`, `RESEARCH-001`, and `EVIDENCE-001` become READY
after it passes; `GHIDRA-001` stays blocked until `DATA-001` passes.

## Exclusions

Do not implement automatic agent launching, worktree creation, agent
scheduling, agent teams, background orchestration, MCP, emulation, AI
reasoning, Ghidra changes, evidence-model changes, or synthetic-firmware
changes.

## Stop

Return the structured handoff and stop. Do not start downstream nodes even if
they become READY.
