# Work Plan

Items are ordered by the supplied build-prompt sequence. Moving an item between
sections requires the preceding prompt's acceptance criteria to pass.

## NOW — Prompt 3: deterministic PyGhidra analysis

- Install or discover a compatible Ghidra/PyGhidra environment.
- Define plain analysis models and an engine-independent adapter interface.
- Analyze one stripped synthetic fixture without reading its ground truth.
- Export functions, memory regions, calls, strings, bytes, and constants as JSON.
- Mark Ghidra integration tests so they skip with a useful reason when absent.
- Score discovered functions against symbols-on addresses only after results are
  saved.

## NEXT

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
- Prompt 2: six reproducible x86-64 Mach-O fixtures, source/ground-truth
  separation, symbols-on and stripped artifacts, behavior probes, metadata,
  exact scoring rules, and 20 laboratory tests.
