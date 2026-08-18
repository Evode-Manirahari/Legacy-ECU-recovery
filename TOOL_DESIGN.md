# Tool Design

The bounded, agent-facing surface over the deterministic static-analysis layer,
delivered by `TOOLS-001`. No model is attached in this node.

## Why this layer exists

The division the project is built on:

> tools derive facts; AI interprets facts; experiments challenge
> interpretations; verification determines correctness.

This file is the first line of that. A tool returns what a deterministic
analyzer observed, in a shape that can be cited later. It never interprets, and
nothing here calls a model.

Attaching a tool surface to an analyzer is only worth doing once the analyzer
has been measured. `EVAL-STATIC-001` did that first: function discovery and
call-graph recovery are exact across all eight synthetic fixtures, with the
recorded baseline in `artifacts/evals/`. That measurement is the license for
this layer, and this node does not repeat it.

## Boundaries

**A tool receives an open session and nothing else.** `ToolContext` has exactly
one field. There is no path, file, directory, or URL argument anywhere in the
surface, so no tool can open, read, or write anything the caller had not already
opened. Choosing what to analyze stays with whoever built the session, which is
not the agent.

**No shell, no arbitrary Python, no network, no filesystem browsing.** These are
excluded by construction rather than by policy: there is no tool that could
express them, and tool names are resolved through a dictionary rather than by
attribute lookup, so an unknown name is a lookup miss and not a route to
something that was never meant to be callable.

**No raw engine objects.** Every response is assembled from the plain records in
`ecu_recovery.analysis.models` through their own `as_dict`, so a Java object
cannot reach a caller. The live tests assert this by round-tripping every result
through JSON.

**No hidden ground truth.** Nothing here reads `firmware.symbols`, the
`ground_truth/` files, or the evaluation harness. A stripped binary yields
`FUN_<address>` names, and a test asserts that is all that ever comes back.

**Bounds come from the analysis layer.** `MAX_RESULTS`, `MAX_INSTRUCTIONS`, and
`MAX_READ_BYTES` are imported from `ecu_recovery.analysis.base` rather than
restated, so the tool surface and the engine cannot drift apart about what "too
much" means.

## Call and response

Every call goes through `ToolRegistry.call(name, context, arguments)`, and
**every call returns a `ToolResult` — no tool raises**. An agent cannot catch a
Python traceback, and a stack trace is not a fact it can reason about.

```json
{"tool": "list_functions", "ok": true,  "data": {...}, "error": null}
{"tool": "list_functions", "ok": false, "data": null, "error": {"code": "invalid_input", "message": "must be >= 1, got 0", "field": "limit"}}
```

The dispatcher validates input against the schema, maps engine exceptions to
codes, then checks the tool's own output against its declared output schema and
size ceiling. A tool that breaks its own contract is caught at the boundary and
reported as `contract_violation` rather than reaching the caller.

### Error codes

| Code | Meaning |
|---|---|
| `unknown_tool` | No such tool. The message lists what exists. |
| `invalid_input` | Arguments failed validation. `field` names the offender. |
| `unknown_function` | No function begins at the given id. |
| `not_found` | A named thing does not exist, such as a memory region. |
| `out_of_bounds` | A read was refused, such as unmapped memory. |
| `session_closed` | The analysis session was closed. |
| `engine_unavailable` | Ghidra or PyGhidra is not installed. |
| `analysis_failed` | The engine failed for another reason. |
| `contract_violation` | A tool broke its own output schema or size ceiling. |
| `internal_error` | Anything unforeseen, with the exception type named. |

### Paging

List answers share one envelope: `returned`, `has_more`, and `next_offset`
(`-1` when there is no next page). Tools that page fetch one item beyond the
request so `has_more` is answered from observation rather than from a count that
might disagree.

A truncated list always says so. A short list that reads as complete is worse
than an error, because it gets reasoned about as if nothing were missing.

## The tools

`*` marks a required argument.

### `binary_summary`
- **Purpose** — what was loaded, how much of it there is, and what the analyzer
  could not establish. The intended first call.
- **Input** — none.
- **Output** — `program`, `function_count`, `memory_region_count`,
  `analysis_warnings`, `analysis_warning_count`.
- **Max output** — 50 warnings; the count is always exact even when the list is
  capped.
- **Failures** — `session_closed`.

### `list_functions`
- **Purpose** — functions ordered by entry address, one page at a time.
- **Input** — `limit` (1–1000, default 100), `offset` (≥ 0, default 0).
- **Output** — `functions`, `returned`, `has_more`, `next_offset`.
- **Max output** — 1000 functions.
- **Failures** — `invalid_input`, `session_closed`.

### `inspect_function`
- **Purpose** — one function's record plus a bounded disassembly listing.
- **Input** — `function_id`*, `instruction_limit` (1–4096, default 64).
- **Output** — `function`, `instructions`, `instruction_count`,
  `instructions_truncated`.
- **Max output** — 4096 instructions.
- **Failures** — `invalid_input`, `unknown_function`, `session_closed`.

Functions are identified by entry address (`0x00001000`). A stripped binary has
no other stable name, which is also why that id is what later evidence cites.

### `decompile_function`
- **Purpose** — decompiler output for one function.
- **Input** — `function_id`*, `timeout_seconds` (1–300, default 30).
- **Output** — `function_id`, `success`, `text`, `text_truncated`, `warnings`.
- **Max output** — 20000 characters of text.
- **Failures** — `invalid_input`, `unknown_function`, `session_closed`.

A failed decompilation is `success: false` with warnings, not an error: which
functions the decompiler could not handle is itself a fact worth reasoning about.

### `get_callers` / `get_callees`
- **Purpose** — the call graph in either direction.
- **Input** — `function_id`*, `limit` (1–1000, default 100).
- **Output** — `function_id`, `callers` / `callees`, plus the paging envelope.
- **Max output** — 1000 functions.
- **Failures** — `invalid_input`, `unknown_function`, `session_closed`.

### `get_cross_references`
- **Purpose** — references that target an address, each citing where it came
  from.
- **Input** — `address`* (`0x`-prefixed string), `limit` (1–1000, default 100).
- **Output** — `address`, `references`, plus the paging envelope.
- **Max output** — 1000 references.
- **Failures** — `invalid_input`, `session_closed`.

### `list_strings`
- **Purpose** — defined strings ordered by address.
- **Input** — `limit` (1–1000, default 100), `offset` (≥ 0, default 0),
  `minimum_length` (1–256, default 4).
- **Output** — `strings`, plus the paging envelope.
- **Max output** — 1000 strings.
- **Failures** — `invalid_input`, `session_closed`.

### `search_constant`
- **Purpose** — where a program uses a value.
- **Input** — `value`* (integer), `limit` (1–1000, default 100).
- **Output** — `value`, `matches`, plus the paging envelope.
- **Max output** — 1000 matches.
- **Failures** — `invalid_input`, `session_closed`.

Two kinds of evidence qualify and are labelled by `kind`: an instruction operand
(`operand`), and a defined data object that code refers to (`data`). **Bytes
that merely equal the value are not a use of it and are never reported.** A
Mach-O header is dense with small integers, and reporting them would manufacture
recoveries no instruction supports. `EVAL-STATIC-001` measured the consequence:
27 of 41 declared fixture constants are recovered under this rule, and inflating
that number would mean weakening what "evidence" means.

### `inspect_memory_region`
- **Purpose** — the loaded memory map, or one named region, optionally with a
  bounded byte window.
- **Input** — `name` (default `""`, meaning all), `include_bytes` (default
  false), `byte_limit` (1–4096, default 256).
- **Output** — `regions`, `bytes`, `bytes_truncated`, plus the paging envelope.
- **Max output** — 1000 regions; the byte window is bounded separately by
  `byte_limit`, capped at `MAX_READ_BYTES`.
- **Failures** — `invalid_input`, `not_found`, `out_of_bounds`,
  `session_closed`.

Reading bytes requires naming exactly one region. This is the route to data a
constant search cannot claim: `EVAL-STATIC-001` found ten fixture constants that
sit in a `__const` table an instruction takes the base address of, reachable
here, named by no operand.

## What this layer deliberately does not do

It does not decide what to analyze, interpret what it returns, rank findings,
score anything against ground truth, or persist evidence. Those belong to later
nodes, and keeping them out is what makes a future interpretation checkable
against the tool output that produced it.
