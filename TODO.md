# Work Plan

Items are ordered by the supplied build-prompt sequence. Moving an item between
sections requires the preceding prompt's acceptance criteria to pass.

## NOW — Prompt 1: engineering scaffold

- Reconcile the current package layout with the required `binary`, `analysis`,
  `agent`, `evidence`, and `reports` package boundaries without breaking the
  existing CLI.
- Configure a reproducible development environment.
- Configure pytest, linting, formatting, and static type checking.
- Add `ecu-recovery doctor`.
- Have doctor check Python, required directories, configuration, Java, and
  optional Ghidra discovery without failing solely because Ghidra is absent.
- Test the doctor command and local installation path.
- Update current-state architecture documentation after implementation.

## NEXT

- Prompt 2: build the six-program synthetic firmware laboratory and metadata.
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

