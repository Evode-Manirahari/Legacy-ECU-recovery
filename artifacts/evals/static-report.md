# Static analysis evaluation — hidden ground truth

**Gate: PASS**

Produced by `EVAL-STATIC-001`. Every fixture was analyzed from
`firmware.stripped` alone; the result was serialized and digested before
the answer key was opened, and the digest was re-checked after scoring.

This report measures the deterministic static-analysis layer. It says
nothing about semantic understanding, which no part of this node evaluates.

## Environment

| Field | Value |
|---|---|
| Engine | ghidra 12.1.2 |
| PyGhidra | 2.2.1 |
| Python | 3.11.15 |
| Platform | Darwin x86_64 |
| Analysis schema | 1 |
| Results schema | 1 |

No timestamp is recorded. The artifact is byte-reproducible on a given
host so a later run can be diffed against it; the commit carrying it is
the record of when it was taken.

## Gate

| Metric | Target | Observed | Result |
|---|---|---|---|
| binary_import | == 100% | 100.0% (8/8) | PASS |
| serialization | == 100% | 100.0% (8/8) | PASS |
| function_discovery_recall | >= 95% | 100.0% (32/32) | PASS |
| function_discovery_precision | >= 95% | 100.0% (32/32) | PASS |
| call_edge_recall | >= 90% | 100.0% (24/24) | PASS |
| unexpected_crashes | == 0 | 0 | PASS |

## Aggregate

Micro-averaged: counts are pooled across fixtures, not averaged as rates,
so a three-function fixture does not outweigh a six-function one.

| Metric | Result |
|---|---|
| Binary import success | 100.0% (8/8) |
| Serialization success | 100.0% (8/8) |
| Function discovery recall | 100.0% (32/32) |
| Function discovery precision | 100.0% (32/32) |
| Function start-address accuracy | 100.0% (32/32) |
| Call-edge recall | 100.0% (24/24) |
| Call-edge precision | 100.0% (24/24) |
| Unexpected analysis crashes | 0 |
| Functions reported outside scoring regions | 0 |

## Constant evidence — reported, not gated

Recovered under the semantic rule: 65.8537% (27/41).

A declared constant the compiler never emitted is a property of the
fixture, not a failure of the analyzer, so this is not a threshold. Raw
matching bytes are not evidence and are not counted anywhere below.

| Evidence class | Count | Counts as recovery |
|---|---:|---|
| `operand` | 20 | yes — an instruction operand carries the value |
| `referenced-data` | 7 | yes — a data object code refers to holds the value |
| `reachable-table-data` | 10 | no — reachable via read_bytes, named by nothing |
| `unsupported` | 4 | no — the compiler emitted no evidence at all |

## Per fixture

### `bitmask_manipulation_v1`

Scoring region: `__text` 0x100000e90-0x100000f9f
Analysis digest: `323f6affc4be3e4f`

| Metric | Result |
|---|---|
| Function discovery recall | 100.0% (5/5) |
| Function discovery precision | 100.0% (5/5) |
| Function start-address accuracy | 100.0% (5/5) |
| Call-edge recall | 100.0% (4/4) |
| Call-edge precision | 100.0% (4/4) |

Reported outside the scoring region: 0 function(s) — compiler or runtime startup code, listed rather than counted as false positives.

Constant evidence — recovered 100.0% (4/4):

| Value | Evidence | Recovered | Detail |
|---|---|---|---|
| 8 | `operand` | yes | 3 instruction operand(s) |
| 15 | `operand` | yes | 1 instruction operand(s) |
| 255 | `operand` | yes | 1 instruction operand(s) |
| 65535 | `operand` | yes | 2 instruction operand(s) |

Analysis warnings:

- `uncovered-executable-bytes` (info) x1
- `uninitialized-memory-block` (info) x1

### `lookup_1d_v1`

Scoring region: `__text` 0x100000ea0-0x100000f7f
Analysis digest: `dc18b195539325f4`

| Metric | Result |
|---|---|
| Function discovery recall | 100.0% (3/3) |
| Function discovery precision | 100.0% (3/3) |
| Function start-address accuracy | 100.0% (3/3) |
| Call-edge recall | 100.0% (2/2) |
| Call-edge precision | 100.0% (2/2) |

Reported outside the scoring region: 0 function(s) — compiler or runtime startup code, listed rather than counted as false positives.

Constant evidence — recovered 81.8182% (9/11):

| Value | Evidence | Recovered | Detail |
|---|---|---|---|
| 0 | `referenced-data` | yes | 2 code-referenced data object(s) |
| 8 | `referenced-data` | yes | 1 code-referenced data object(s) |
| 19 | `referenced-data` | yes | 1 code-referenced data object(s) |
| 20 | `referenced-data` | yes | 1 code-referenced data object(s) |
| 33 | `referenced-data` | yes | 1 code-referenced data object(s) |
| 40 | `referenced-data` | yes | 1 code-referenced data object(s) |
| 52 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 60 | `referenced-data` | yes | 1 code-referenced data object(s) |
| 75 | `operand` | yes | 3 instruction operand(s) |
| 80 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 100 | `operand` | yes | 1 instruction operand(s) |

Analysis warnings:

- `uncovered-executable-bytes` (info) x1
- `uninitialized-memory-block` (info) x1

### `lookup_2d_v1`

Scoring region: `__text` 0x100000ea0-0x100000f6f
Analysis digest: `c4621e07d12d2a6e`

| Metric | Result |
|---|---|
| Function discovery recall | 100.0% (4/4) |
| Function discovery precision | 100.0% (4/4) |
| Function start-address accuracy | 100.0% (4/4) |
| Call-edge recall | 100.0% (3/3) |
| Call-edge precision | 100.0% (3/3) |

Reported outside the scoring region: 0 function(s) — compiler or runtime startup code, listed rather than counted as false positives.

Constant evidence — recovered 38.4615% (5/13):

| Value | Evidence | Recovered | Detail |
|---|---|---|---|
| 2 | `operand` | yes | 4 instruction operand(s) |
| 3 | `operand` | yes | 1 instruction operand(s) |
| 10 | `operand` | yes | 1 instruction operand(s) |
| 12 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 14 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 15 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 18 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 19 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 22 | `operand` | yes | 1 instruction operand(s) |
| 24 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 26 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 30 | `reachable-table-data` | no | int32 slot in code-referenced region __const; reachable through read_bytes but named by no operand or data object |
| 36 | `operand` | yes | 1 instruction operand(s) |

Analysis warnings:

- `uncovered-executable-bytes` (info) x1
- `uninitialized-memory-block` (info) x1

### `multi_function_pipeline_v1`

Scoring region: `__text` 0x100000eb0-0x100000fa7
Analysis digest: `a6e9ccabc44eb80e`

| Metric | Result |
|---|---|
| Function discovery recall | 100.0% (6/6) |
| Function discovery precision | 100.0% (6/6) |
| Function start-address accuracy | 100.0% (6/6) |
| Call-edge recall | 100.0% (5/5) |
| Call-edge precision | 100.0% (5/5) |

Reported outside the scoring region: 0 function(s) — compiler or runtime startup code, listed rather than counted as false positives.

Constant evidence — recovered 66.6667% (2/3):

| Value | Evidence | Recovered | Detail |
|---|---|---|---|
| 0 | `unsupported` | no | no operand, no referenced data object, and no code-referenced region slot |
| 100 | `operand` | yes | 2 instruction operand(s) |
| 1000 | `operand` | yes | 4 instruction operand(s) |

Analysis warnings:

- `uncovered-executable-bytes` (info) x1
- `uninitialized-memory-block` (info) x1

### `rpm_calculation_v1`

Scoring region: `__text` 0x100000f10-0x100000fb7
Analysis digest: `87f2ae43198c9c43`

| Metric | Result |
|---|---|
| Function discovery recall | 100.0% (3/3) |
| Function discovery precision | 100.0% (3/3) |
| Function start-address accuracy | 100.0% (3/3) |
| Call-edge recall | 100.0% (2/2) |
| Call-edge precision | 100.0% (2/2) |

Reported outside the scoring region: 0 function(s) — compiler or runtime startup code, listed rather than counted as false positives.

Constant evidence — recovered 50.0% (1/2):

| Value | Evidence | Recovered | Detail |
|---|---|---|---|
| 0 | `unsupported` | no | no operand, no referenced data object, and no code-referenced region slot |
| 60 | `operand` | yes | 1 instruction operand(s) |

Analysis warnings:

- `uncovered-executable-bytes` (info) x1
- `uninitialized-memory-block` (info) x1

### `state_machine_v1`

Scoring region: `__text` 0x100000ef0-0x100000fab
Analysis digest: `9bee39aec79de382`

| Metric | Result |
|---|---|
| Function discovery recall | 100.0% (3/3) |
| Function discovery precision | 100.0% (3/3) |
| Function start-address accuracy | 100.0% (3/3) |
| Call-edge recall | 100.0% (2/2) |
| Call-edge precision | 100.0% (2/2) |

Reported outside the scoring region: 0 function(s) — compiler or runtime startup code, listed rather than counted as false positives.

Constant evidence — recovered 80.0% (4/5):

| Value | Evidence | Recovered | Detail |
|---|---|---|---|
| 0 | `unsupported` | no | no operand, no referenced data object, and no code-referenced region slot |
| 1 | `operand` | yes | 5 instruction operand(s) |
| 2 | `operand` | yes | 5 instruction operand(s) |
| 3 | `operand` | yes | 3 instruction operand(s) |
| 600 | `operand` | yes | 1 instruction operand(s) |

Analysis warnings:

- `uncovered-executable-bytes` (info) x1
- `uninitialized-memory-block` (info) x1

### `temperature_controller_v1`

Scoring region: `__text` 0x100000f40-0x100000fb7
Analysis digest: `116ad69926240115`

| Metric | Result |
|---|---|
| Function discovery recall | 100.0% (3/3) |
| Function discovery precision | 100.0% (3/3) |
| Function start-address accuracy | 100.0% (3/3) |
| Call-edge recall | 100.0% (2/2) |
| Call-edge precision | 100.0% (2/2) |

Reported outside the scoring region: 0 function(s) — compiler or runtime startup code, listed rather than counted as false positives.

Constant evidence — recovered 50.0% (1/2):

| Value | Evidence | Recovered | Detail |
|---|---|---|---|
| 0 | `unsupported` | no | no operand, no referenced data object, and no code-referenced region slot |
| 1 | `operand` | yes | 1 instruction operand(s) |

Analysis warnings:

- `uncovered-executable-bytes` (info) x1
- `uninitialized-memory-block` (info) x1

### `timer_counter_v1`

Scoring region: `__text` 0x100000e80-0x100000f9f
Analysis digest: `ac26fc403a2340e3`

| Metric | Result |
|---|---|
| Function discovery recall | 100.0% (5/5) |
| Function discovery precision | 100.0% (5/5) |
| Function start-address accuracy | 100.0% (5/5) |
| Call-edge recall | 100.0% (4/4) |
| Call-edge precision | 100.0% (4/4) |

Reported outside the scoring region: 0 function(s) — compiler or runtime startup code, listed rather than counted as false positives.

Constant evidence — recovered 100.0% (1/1):

| Value | Evidence | Recovered | Detail |
|---|---|---|---|
| 3000 | `operand` | yes | 2 instruction operand(s) |

Analysis warnings:

- `uncovered-executable-bytes` (info) x1
- `uninitialized-memory-block` (info) x1
