# Work Plan

Items are ordered by the supplied build-prompt sequence. Moving an item between
sections requires the preceding prompt's acceptance criteria to pass.

## NOW — Prompt 2: synthetic firmware laboratory

- Select and document one architecture based on compiler, Ghidra, documentation,
  and future-emulator availability.
- Build six known-source embedded C programs with reproducible compiler settings.
- Preserve symbols-on and symbols-stripped builds separately.
- Store machine-readable ground truth away from investigator-visible artifacts.
- Validate every binary-to-metadata relationship with tests.
- Define exact reverse-engineering accuracy scoring against the fixtures.

## NEXT

- Prompt 3: add deterministic PyGhidra analysis for the chosen architecture.
- Prompt 4: introduce bounded, validated Python investigation tools.
- Prompt 5: expose stable tools through a local, least-privilege MCP server.
- Prompts 6–9: investigator, persistent evidence memory, evaluation harness,
  and structured engineering report.

## LATER

- Prompts 10–15: synthetic CPU emulation, controlled experiments, minimal
  peripherals, human-approved agent experiments, one-function C reconstruction,
  and context engineering.
- Prompts 16–18: sandbox hardening, observability, and a thin product interface.
- Prompts 19–22: real-firmware readiness review, approved target research,
  authorized demonstration, and product-value measurement.
- Automatic architecture detection, broader architecture support, and any
  deployment-oriented capability require separate evidence and authorization.

## COMPLETED

- Prompt 0: persistent engineering contract, evaluation plan, and threat model.
- Prompt 1: Python package boundaries, uv lockfile, pytest, Ruff, strict mypy,
  minimal CLI, environment doctor, and unit tests.
