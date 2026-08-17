# NODE: REPO-001

**Title:** Reproducible Python engineering infrastructure
**Depends on:** `SPEC-001`
**Status:** PASSED (2026-08-17)
**Verification:** commands
**Retry budget:** 2

## Goal

Establish reproducible Python engineering infrastructure.

## Ownership

Allowed: `pyproject.toml`, `src/ecu_recovery/**`, `tests/**`,
`.github/workflows/**`.

Forbidden: `samples/**`, `scripts/build_synthetic.py`, `graph/**`,
`prompts/**`.

## Deliverables

- Python package layout under `src/`.
- `pyproject.toml`.
- pytest.
- Ruff.
- One strict static type checker.
- CLI entry point.
- `ecu-recovery doctor` reporting Python version, project configuration, Java
  availability, Ghidra discoverability, and required directory state.
- Basic CI configuration.

A missing Ghidra must never cause the repository itself to fail.

## Acceptance

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Exclusions

Do not implement AI, Ghidra integration, emulation, a frontend, or MCP.

## Execution note

This is an existing repository. Audit each requirement as SATISFIED,
PARTIALLY_SATISFIED, MISSING, or CONFLICTING before changing anything, and
implement only what is missing or incorrect. Existing code is candidate
implementation, not proof of completion.

## Stop

Return the structured handoff and stop.
