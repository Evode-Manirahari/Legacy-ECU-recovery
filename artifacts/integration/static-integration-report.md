# Static MVP integration

**Flow: PASS**

Produced by `INTEGRATION-STATIC-001`. Each fixture below was driven through
the whole static stack using the merged public interfaces of the upstream
passed nodes. Nothing upstream is stubbed or reimplemented here: a stub would
prove only that the stub works.

```text
stripped binary -> Ghidra analysis -> internal models -> bounded tool layer
    -> evidence persistence -> evaluation
```

Functions are persisted from what the *tool layer* reported rather than from
the analysis session, because the boundary between those two is what this
node exists to test.

## Steps

| Fixture | Step | Result | Detail |
|---|---|---|---|
| `multi_function_pipeline_v1` | intake | PASS | sha256=8430fb8e8ef223f6 size=4216 |
| `multi_function_pipeline_v1` | ghidra-analysis | PASS | functions=6 engine=12.1.2 |
| `multi_function_pipeline_v1` | internal-models | PASS | schema=1 edges=5 |
| `multi_function_pipeline_v1` | bounded-tools | PASS | functions=6 edges=5 constant_matches=4 |
| `multi_function_pipeline_v1` | evidence-persistence | PASS | evidence=9 relationships=5 revisions=2 |
| `multi_function_pipeline_v1` | evaluation | PASS | gate=PASS digest=24fa4947cdd7e940 |
| `lookup_1d_v1` | intake | PASS | sha256=5c7b009d3626f55e size=4216 |
| `lookup_1d_v1` | ghidra-analysis | PASS | functions=3 engine=12.1.2 |
| `lookup_1d_v1` | internal-models | PASS | schema=1 edges=2 |
| `lookup_1d_v1` | bounded-tools | PASS | functions=3 edges=2 constant_matches=1 |
| `lookup_1d_v1` | evidence-persistence | PASS | evidence=3 relationships=2 revisions=2 |
| `lookup_1d_v1` | evaluation | PASS | gate=PASS digest=66b2ba63c0702486 |

## Boundary crossings

| Fixture | Crossing | Observed |
|---|---|---|
| `multi_function_pipeline_v1` | analysis functions -> tool functions | 6 -> 6 |
| `multi_function_pipeline_v1` | tool functions -> stored functions | 6 -> 6 |
| `multi_function_pipeline_v1` | tool call edges -> stored relationships | 5 -> 5 |
| `multi_function_pipeline_v1` | tool findings -> evidence rows | 9 |
| `multi_function_pipeline_v1` | hypothesis revisions preserved | 2 |
| `multi_function_pipeline_v1` | evaluation call-edge recall | 100.0% (5/5) |
| `lookup_1d_v1` | analysis functions -> tool functions | 3 -> 3 |
| `lookup_1d_v1` | tool functions -> stored functions | 3 -> 3 |
| `lookup_1d_v1` | tool call edges -> stored relationships | 2 -> 2 |
| `lookup_1d_v1` | tool findings -> evidence rows | 3 |
| `lookup_1d_v1` | hypothesis revisions preserved | 2 |
| `lookup_1d_v1` | evaluation call-edge recall | 100.0% (2/2) |

## Warnings

- `multi_function_pipeline_v1` ghidra-analysis: uncovered-executable-bytes:info
- `multi_function_pipeline_v1` ghidra-analysis: uninitialized-memory-block:info
- `lookup_1d_v1` ghidra-analysis: uncovered-executable-bytes:info
- `lookup_1d_v1` ghidra-analysis: uninitialized-memory-block:info

## Interface mismatches

Observed across 2 fixtures. Each is a property of an interface rather than of a binary, so each is listed once.

- `BinaryAnalysis.as_dict()["program"]["source_path"]` is an absolute host path. That is GHIDRA-001 behaviour and harmless in memory, but any consumer persisting it into a reproducible artifact inherits the checkout directory. EVAL-STATIC-001 already had to normalise it locally (PR #15), so the workaround lives in the consumer rather than at the source and every future consumer must remember it.

## Refused tool calls

A refused call must stay a refusal. These were issued deliberately and
produced no evidence row.

- `multi_function_pipeline_v1` `inspect_function` -> `unknown_function` (field `function_id`)
- `lookup_1d_v1` `inspect_function` -> `unknown_function` (field `function_id`)

## Open blockers

A blocker stops the static MVP. The findings above are interface
observations: the flow completed, every citation resolved, and the
evaluation gate passed with them present.

None.

## Performance

Wall-clock, and therefore the one part of this report that does not
reproduce byte for byte. Everything above this heading does.

| Fixture | Step | Seconds |
|---|---|---:|
| `multi_function_pipeline_v1` | intake | 0.00 |
| `multi_function_pipeline_v1` | ghidra-analysis | 0.04 |
| `multi_function_pipeline_v1` | internal-models | 0.05 |
| `multi_function_pipeline_v1` | bounded-tools | 0.04 |
| `multi_function_pipeline_v1` | evidence-persistence | 0.08 |
| `multi_function_pipeline_v1` | evaluation | 0.90 |
| `lookup_1d_v1` | intake | 0.00 |
| `lookup_1d_v1` | ghidra-analysis | 0.00 |
| `lookup_1d_v1` | internal-models | 0.00 |
| `lookup_1d_v1` | bounded-tools | 0.02 |
| `lookup_1d_v1` | evidence-persistence | 0.08 |
| `lookup_1d_v1` | evaluation | 0.86 |
