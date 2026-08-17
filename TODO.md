# Work Plan

Items are ordered by the supplied build-prompt sequence. Moving an item between
sections requires the preceding prompt's acceptance criteria to pass.

## NOW — Prompt 4: bounded, validated agent tools

- Wrap the session capabilities as narrowly scoped tools with structured input
  and output, building on the bounds already in `analysis/base.py`.
- Give every tool explicit validation and typed failures rather than tracebacks.
- Write `TOOL_DESIGN.md` recording purpose, input, output, failure cases, and
  maximum output size for each tool.
- Cover invalid input and oversized results with tests.
- Keep the layer free of any model dependency.

## NEXT

- Prompt 5: expose stable tools through a local, least-privilege MCP server.
- Prompts 6–9: investigator, persistent evidence memory, evaluation harness,
  and structured engineering report.

## Known gaps carried forward

- Intake rejects extension-free files. Raw ROM dumps frequently have no
  extension, so the allowlist needs a decision before Prompt 21.
- Ghidra parses untrusted binaries in our own process. Prompt 16 must decide
  between accepting this, sandboxing the JVM, or moving to a headless subprocess.
- `--base-address` sets the image base for a raw dump but is only exercised
  against Mach-O fixtures that carry their own base. It needs a raw-binary
  fixture before it can be called verified.
- Function classification, evidence validity, and confidence calibration from
  `docs/synthetic-lab.md` are defined but unmeasured; they need Prompt 8's
  harness.

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
- Prompt 3: engine-free analysis models, a bounded `StaticAnalysisEngine` /
  `StaticAnalysisSession` interface, a PyGhidra implementation of all thirteen
  capabilities, JSON export, `analyze --ghidra`, stricter Ghidra discovery, and
  24 Ghidra integration tests that skip with a reason when Ghidra is absent
  (81 tests total; 57 run without Ghidra).
