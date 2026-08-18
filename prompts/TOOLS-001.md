# NODE: TOOLS-001

**Title:** Bounded agent-facing analysis tools
**Depends on:** `EVAL-STATIC-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Wrap static-analysis capabilities in bounded, structured functions suitable for
a future AI agent. No model is attached in this node.

## Ownership

Allowed: `src/ecu_recovery/tools/**`, `tests/tools/**`, `TOOL_DESIGN.md`.

Forbidden: `src/ecu_recovery/analysis/**`, `graph/**`, `samples/**`.

## Initial tools

```text
binary_summary
list_functions
inspect_function
decompile_function
get_callers
get_callees
get_cross_references
list_strings
search_constant
inspect_memory_region
```

## Every tool must have

Name, description, input schema, output schema, validation, bounded output
size, and a structured error response.

Build on the bounds already defined in `ecu_recovery.analysis.base`
(`MAX_READ_BYTES`, `MAX_INSTRUCTIONS`, `MAX_RESULTS`) rather than inventing new
ones.

## Deliverables

The tool layer plus `TOOL_DESIGN.md` recording purpose, input, output, failure
cases, and maximum output size for each tool.

## Acceptance

```bash
uv run pytest
```

Tests must cover valid input, invalid input, oversized requests, tool failure,
and pagination.

## Exclusions

Do not give the future agent arbitrary shell, arbitrary Python, unrestricted
filesystem access, or network access as a substitute for proper tools. Do not
add an LLM. Do not add MCP.

## Stop

Return the structured handoff and stop.
