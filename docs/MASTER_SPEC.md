---
title: "Legacy ECU Recovery"
subtitle: "Master Graph Engineering Build Specification"
author: "Project Working Specification"
date: "2026-08-17"
version: "1.1"
---

# Document status

**Status:** Ready for execution  
**Repository authority:** `docs/MASTER_SPEC.md`  
**Published copy:** `MASTER_SPEC.pdf`  
**Current development state:** `SPEC-001 = PASSED`, `REPO-001 = PASSED`, `GRAPH-001 = READY`

> The Markdown file in the repository is the authoritative machine-readable source for coding agents. The PDF is a human-readable companion for review, sharing, and planning. If the two ever differ, the repository Markdown wins.

# 1. Executive summary

The project is an AI-assisted engineering system for understanding legally obtained legacy ECU and embedded firmware when source code, documentation, build systems, or original engineers are missing.

The initial product is not an automatic replacement-firmware generator. The first useful product is:

```text
Binary -> static analysis -> evidence-backed understanding -> engineering report
```

The later product becomes:

```text
Binary
  -> static analysis
  -> hypotheses
  -> controlled experiments
  -> behavioral understanding
  -> selected C reconstruction
  -> behavioral verification
```

The build method is graph engineering:

> **Graph outside. Loops inside. Tests on the edges.**

Global work is controlled by an explicit dependency DAG. Coding agents receive bounded nodes. A node is complete only when its acceptance conditions pass. Local implement-test-debug loops are encouraged inside a node, but an agent must not autonomously move into downstream nodes.

# 2. The problem

Legacy embedded software often outlives the team and infrastructure that created it. A company may still depend on a controller while possessing only some combination of:

- a physical ECU or controller;
- a raw firmware image;
- partial service documentation;
- old calibration or diagnostic files;
- incomplete hardware notes;
- tribal knowledge from a few engineers.

What may be missing:

- original source code;
- symbols;
- build scripts;
- compiler version;
- design specification;
- test suite;
- hardware abstraction documentation;
- original developers.

Reverse engineers then spend substantial time discovering functions, data structures, state machines, calibration tables, communication routines, control logic, and hardware assumptions manually.

The project bet is:

> An evidence-driven AI engineering system can automate enough repetitive firmware investigation to reduce expert engineering time while preserving traceability, uncertainty, and human control.

# 3. First product and first customer

## 3.1 First product

Input:

```text
firmware.bin
```

Useful early output:

- processor and architecture metadata;
- memory map;
- entry points and interrupt candidates;
- function inventory;
- call graph;
- cross references;
- strings and constants;
- data/table candidates;
- calibration candidates;
- diagnostic and communication candidates;
- function explanations;
- C-like pseudocode where useful;
- evidence for each claim;
- confidence and uncertainty;
- contradictions and unresolved questions;
- generated engineering report.

The first product does **not** require perfect C reconstruction.

## 3.2 Early customer categories

Potential early users include:

- ECU remanufacturers;
- automotive electronics specialists;
- embedded reverse engineers;
- engineering consultancies;
- suppliers maintaining discontinued products;
- motorsport electronics teams;
- classic-car electronics specialists;
- firmware security teams;
- industrial embedded maintenance teams.

The preferred discovery question is:

> Show me the last embedded controller that took you days or weeks to understand.

Then measure what consumed time, what evidence they trusted, where uncertainty occurred, and which repetitive steps could be accelerated.

# 4. Scope and non-goals

## 4.1 Initial scope

Start narrow:

```text
one supported CPU architecture
-> one synthetic benchmark family
-> one selected ECU family
-> one authorized real firmware case
```

Do not start by supporting every architecture or OEM.

## 4.2 Explicit non-goals for the early product

Do not build these before the required gates:

- full vehicle simulation;
- firmware flashing;
- live vehicle control;
- automated tuning;
- immobilizer bypass;
- credential or key extraction;
- arbitrary host execution;
- perfect whole-firmware source recovery;
- multi-OEM enterprise infrastructure;
- a large autonomous agent team;
- a front end before the analysis primitive is proven.

# 5. Core product principle: testable claims

The system should not optimize for fluent explanations. It should optimize for claims that can be checked.

```text
OBSERVE
   |
   v
HYPOTHESIZE
   |
   v
TEST
   |
   v
COLLECT EVIDENCE
   |
   v
UPDATE BELIEF
   |
   v
VERIFY
```

Every important conclusion should eventually point to concrete evidence such as:

- decompiler output;
- disassembly;
- call relationships;
- cross references;
- memory reads/writes;
- constants;
- table accesses;
- execution traces;
- controlled experiment results;
- expert review.

# 6. Why graph engineering

The project has hard dependencies. A mistake at one layer can invalidate everything above it.

```text
Bad static analysis
        |
        v
Bad hypotheses
        |
        v
Bad experiments
        |
        v
Bad reconstruction
```

Therefore progress is measured by **verified dependency completion**, not agent activity.

The global development structure is a Directed Acyclic Graph (DAG).

A node is one bounded engineering objective.

An edge means:

> The prerequisite was verified.

An edge does not mean:

> The previous agent said it was done.

# 7. Research basis

This specification uses current agent-engineering research and practitioner material as guidance, not as doctrine.

## 7.1 Andrew Ng / DeepLearning.AI - Agentic AI

Andrew Ng's Agentic AI course teaches reflection, tool use, planning, multi-agent workflows, and systematic evaluation/error analysis. The project adopts the principle that autonomy should be expanded only after measurable evaluation exists.

Source: DeepLearning.AI, "Agentic AI" course, instructor Andrew Ng.  
https://www.deeplearning.ai/courses/agentic-ai

## 7.2 Anthropic - long-running agent harnesses

Anthropic's engineering work on long-running agents emphasizes incremental units of work, persistent artifacts, explicit handoffs, verification, and harnesses that evolve as models improve.

Relevant primary sources:

- "Effective harnesses for long-running agents" - Anthropic Engineering.
- "Harness design for long-running application development" - Anthropic Engineering.
- "Scaling Managed Agents: Decoupling the brain from the hands" - Anthropic Engineering.

The project adopts:

> Persistent state and explicit interfaces should outlive any particular agent harness.

## 7.3 Claude Code worktrees and parallel agents

Claude Code documents worktrees as isolated Git checkouts for parallel sessions and distinguishes worktrees, subagents, agent view, agent teams, and batch workflows.

Source: Claude Code documentation, "Run parallel sessions with worktrees" and "Run agents in parallel."  
https://code.claude.com/docs/en/worktrees  
https://code.claude.com/docs/en/agents

The project adopts:

> Parallelize independent work in isolated worktrees; do not create parallel workers around the same bottleneck.

## 7.4 Anthropic parallel compiler experiment

Anthropic reported a 2026 experiment in which a team of parallel Claude Code sessions built a large C compiler. The useful lesson for this project is not "use many agents." It is that parallelism works best when work is decomposable and test harnesses provide strong failure signals.

Source: Anthropic Engineering, "Building a C compiler with a team of parallel Claudes."  
https://www.anthropic.com/engineering/building-c-compiler

## 7.5 LoopsBench

LoopsBench represents long-horizon software tasks as dependency DAGs over separately testable development units and retains completed tests as regression obligations.

Source: Li et al., "LoopsBench: From Harness Engineering to Loop Engineering in Coding Agent Evaluation," arXiv:2608.00267, 2026.  
https://arxiv.org/abs/2608.00267

The project adopts:

> Previously passed nodes create continuing regression obligations.

## 7.6 AgentFlow and repository graph research

AgentFlow describes framework-agnostic Agent Dependency Graphs with typed nodes and dependency/control/data-flow edges. Repository Intelligence Graph research studies deterministic repository/build graphs as context for coding assistants.

Sources:

- "AgentFlow: Building Agent Dependency Graphs for Static Analysis of Agent Programs," arXiv:2607.01640.
- "Repository Intelligence Graph: Deterministic Architectural Map for LLM Code Assistants," arXiv:2601.10112.

These sources support explicit structure, but do not prove that one fixed graph design is always optimal.

## 7.7 Andrej Karpathy - partial autonomy

Karpathy's "Software Is Changing (Again)" frames LLMs as a new software layer with unusual strengths and weaknesses. The project follows a partial-autonomy design: use models for reasoning and synthesis, deterministic software for checks that can be computed, and humans for high-consequence approval.

Source: Andrej Karpathy, "Software Is Changing (Again)," AI Startup School, 2025.  
https://www.youtube.com/watch?v=LCEmiRjPEtQ

## 7.8 Research rule

Graph engineering is a current engineering hypothesis, not a permanent ideology. After every major gate, review whether a node should remain:

- deterministic code;
- one coding agent;
- one agent with a local repair loop;
- several parallel workers;
- planner plus worker plus evaluator;
- human-led.

If measurements show a simpler approach is better, change the graph.

# 8. Three graphs in this project

Do not confuse the three graph types.

## 8.1 Graph A - Development graph

Purpose: build the product.

```text
SPEC
  -> repository
  -> graph infrastructure
  -> synthetic firmware / research / evidence
  -> Ghidra
  -> evaluation
  -> tools
  -> investigator
  -> emulator
  -> experiments
  -> reconstruction
```

This is the graph currently being implemented.

## 8.2 Graph B - Firmware investigation graph

Purpose: control how the product investigates firmware.

```text
Firmware
   -> static analysis
   -> evidence join
   -> hypothesis
   -> confidence check
       | high -> document
       | low  -> experiment planner
                  -> validator
                  -> emulator
                  -> evidence
                  -> revise hypothesis
```

This comes later.

## 8.3 Graph C - Firmware knowledge graph

Purpose: represent accumulated understanding.

```text
FUN_923A
   |-- READS ----------> RAM_0244
   |-- CALLS ----------> FUN_A441
   |-- ACCESSES -------> TABLE_B440
   `-- MAY_IMPLEMENT --> RPM_CALCULATION
```

Knowledge edges may carry:

- confidence;
- evidence IDs;
- experiment IDs;
- source;
- timestamp;
- review state.

This graph represents knowledge. It does not control execution.

# 9. Development stack

## 9.1 Primary languages

**Python** for:

- orchestration;
- Ghidra integration;
- data models;
- evidence persistence;
- agent tools;
- experiments;
- evaluation;
- reporting.

**C** for:

- synthetic embedded fixtures;
- reconstructed firmware behavior;
- behavioral comparison targets.

**C/C++** only where emulator or performance integration requires it.

## 9.2 Tooling

Initial stack:

- Python 3.11+;
- Git;
- Claude Code or equivalent coding agent;
- Git worktrees;
- pytest;
- Ruff;
- mypy or one selected strict type checker;
- Ghidra;
- PyGhidra;
- SQLite;
- YAML graph definition;
- a small Python DAG implementation initially;
- emulator selected later based on target architecture.

Candidate emulation engines include Unicorn, QEMU, or an architecture-specific emulator. The rest of the product should depend on an abstract emulator interface rather than a vendor-specific implementation.

# 10. Repository layout

Target layout:

```text
ecu-recovery/
|
|-- README.md
|-- PROJECT.md
|-- ARCHITECTURE.md
|-- DECISIONS.md
|-- TODO.md
|-- EVALS.md
|-- THREAT_MODEL.md
|-- RESEARCH.md
|-- ecu-project.graph.yaml
|-- pyproject.toml
|
|-- docs/
|   `-- MASTER_SPEC.md
|
|-- graph/
|   |-- __init__.py
|   |-- models.py
|   |-- state.py
|   |-- loader.py
|   |-- validator.py
|   `-- status.py
|
|-- prompts/
|   |-- SPEC-001.md
|   |-- REPO-001.md
|   |-- GRAPH-001.md
|   |-- DATA-001.md
|   |-- RESEARCH-001.md
|   |-- EVIDENCE-001.md
|   |-- GHIDRA-001.md
|   |-- EVAL-STATIC-001.md
|   |-- TOOLS-001.md
|   |-- INTEGRATION-STATIC-001.md
|   `-- GATE-STATIC-MVP.md
|
|-- src/ecu_recovery/
|   |-- binary/
|   |-- analysis/
|   |-- evidence/
|   |-- agent/
|   |-- emulator/
|   |-- experiments/
|   |-- reconstruction/
|   `-- reports/
|
|-- samples/synthetic/
|   |-- source/
|   |-- binaries/
|   `-- ground_truth/
|
|-- tests/
|-- scripts/
|-- artifacts/
`-- .github/workflows/
```

Directories that belong to future nodes should not be created merely to make the tree look complete.

# 11. Node state machine

Valid development node states:

```text
PENDING
READY
RUNNING
VERIFYING
PASSED
FAILED
BLOCKED
NEEDS_HUMAN
UNVERIFIED-UNDER-GRAPH
```

Conceptual transition:

```text
PENDING
   | all dependencies PASSED
   v
READY
   | worker assigned
   v
RUNNING
   | worker finishes
   v
VERIFYING
   |-- checks pass ----------> PASSED
   |-- checks fail ----------> FAILED
   `-- external dependency --> BLOCKED
```

Repeated failure beyond retry budget becomes `NEEDS_HUMAN`.

# 12. Node contract

Every coding node should define:

```text
NODE ID
TITLE
GOAL
RATIONALE
DEPENDENCIES
INPUT ARTIFACTS
ALLOWED FILES
FORBIDDEN FILES
ALLOWED TOOLS
DELIVERABLES
ACCEPTANCE TESTS
EVALUATION REQUIREMENTS
RETRY BUDGET
OUTPUT ARTIFACTS
HANDOFF SCHEMA
TERMINAL STATES
```

A node must not be marked complete because the implementation looks plausible.

# 13. Structured handoff contract

Every coding node returns a structured handoff. Example:

```json
{
  "node_id": "GHIDRA-001",
  "status": "VERIFYING",
  "commit_sha": null,
  "base_commit": "abc123",
  "artifacts": [
    "src/ecu_recovery/analysis/ghidra.py"
  ],
  "tests_run": [
    "uv run pytest tests/analysis"
  ],
  "test_results": {
    "passed": 21,
    "failed": 0
  },
  "known_failures": [],
  "blockers": [],
  "assumptions": [],
  "interfaces_added": [
    "analyze_binary",
    "list_functions"
  ],
  "next_node_inputs": [
    "analysis-result.json"
  ]
}
```

Downstream agents should not depend only on informal prose summaries.

# 14. Verification hierarchy

Prefer verification in this order.

## Level 1 - Deterministic verification

Examples:

- test result;
- compiler result;
- schema validation;
- binary comparison;
- graph validation;
- behavioral comparison.

## Level 2 - Hidden ground truth

Use controlled fixtures where expected functions, addresses, calls, constants, and behavior are known but hidden from the analysis agent.

## Level 3 - Human expert review

Use when domain judgment is necessary.

## Level 4 - LLM judge

Use only where the property cannot reasonably be evaluated by deterministic or expert means.

Rule:

> If software can prove it, do not ask another model whether it looks correct.

# 15. Regression obligations

Once a node passes, its verification remains active downstream.

```text
GHIDRA tests
   +
TOOLS tests
   +
AGENT tests
   +
EMU tests
   |
   v
CURRENT SYSTEM VALIDATION
```

A later node that breaks an earlier verified property fails the current build.

# 16. Retry and failure policy

Default retry budget for coding nodes:

```text
retry_budget: 2
```

Flow:

```text
attempt
  -> failure evidence
  -> repair
  -> retest
```

After the retry budget, return `NEEDS_HUMAN`.

Do not create endless autonomous loops.

Failure data must be preserved, including:

- failed experiments;
- wrong hypotheses;
- compiler errors;
- tool failures;
- emulator crashes;
- contradictory evidence;
- failed reconstruction candidates.

# 17. Parallelism and worktrees

Parallelize only independent nodes with disjoint ownership.

Good:

```text
GRAPH-001 PASSED
       |
       +------------+------------+
       |            |            |
       v            v            v
   DATA-001    RESEARCH-001  EVIDENCE-001
```

Bad:

```text
Agent A --\
Agent B ----> all modifying the same Ghidra adapter
Agent C --/
```

Each parallel coding worker should receive:

```text
one node
one worktree
one branch
one ownership area
one acceptance contract
```

Example Claude Code commands after the fan-out is authorized:

```bash
claude --worktree data-001
claude --worktree research-001
claude --worktree evidence-001
```

Initial parallelism cap: three workers.

# 18. Current development graph

As of 2026-08-17:

```text
SPEC-001       PASSED
    |
    v
REPO-001       PASSED
    |
    v
GRAPH-001      READY
    |
    +------------------+------------------+
    |                  |                  |
    v                  v                  v
DATA-001          RESEARCH-001       EVIDENCE-001
    |
    v
GHIDRA-001
    |
    v
EVAL-STATIC-001
    |
    v
TOOLS-001
    |
    v
INTEGRATION-STATIC-001
    |
    v
GATE-STATIC-MVP
```

Pre-graph code is treated as candidate implementation and remains `UNVERIFIED-UNDER-GRAPH` until its node contract is executed.

# 19. Completed foundation nodes

## 19.1 SPEC-001 - PASSED

Purpose: establish the project contract, architecture, decisions, evaluation policy, threat model, research log, and work queue.

Primary artifacts:

- `PROJECT.md`;
- `ARCHITECTURE.md`;
- `DECISIONS.md`;
- `TODO.md`;
- `EVALS.md`;
- `THREAT_MODEL.md`;
- `RESEARCH.md`.

Human approval is required because this node defines project policy.

## 19.2 REPO-001 - PASSED

Purpose: establish reproducible Python engineering infrastructure.

Verified capabilities include:

- Python package layout;
- `pyproject.toml`;
- pytest;
- Ruff;
- strict mypy;
- CLI entry point;
- `ecu-recovery doctor`;
- graceful operation when optional Ghidra tooling is unavailable;
- basic CI configuration.

Existing Ghidra, data, and evidence code from pre-graph work is not grandfathered in as passed; it must be re-verified in its own node.

# 20. GRAPH-001 - next node

## 20.1 Goal

Implement the minimum infrastructure required to represent, validate, and inspect the development dependency graph.

Do not build a full autonomous agent orchestrator.

Version 1 needs to answer:

- What nodes exist?
- What does each node depend on?
- Is the graph acyclic?
- Do dependencies reference real nodes?
- Which nodes are READY?
- Which nodes are BLOCKED?
- Which nodes are PASSED?
- What becomes READY after a node passes?

## 20.2 Ownership

`GRAPH-001` owns:

```text
ecu-project.graph.yaml
graph/**
prompts/**
artifacts/**
tests/graph/**
```

It may update `TODO.md` and `ARCHITECTURE.md` only enough to record the graph implementation.

## 20.3 Required node fields

The graph schema must support at least:

```text
id
title
depends_on
status
worker
prompt
allowed_paths
verification
retry_budget
```

## 20.4 Validation rules

The graph validator must reject:

- cycles;
- duplicate node IDs;
- unknown dependencies;
- invalid state values;
- self-dependencies.

## 20.5 Required tests

At minimum:

- valid graph loads;
- cycle rejected;
- unknown dependency rejected;
- self-dependency rejected;
- invalid status rejected;
- `SPEC-001` and `REPO-001` read as passed;
- `GRAPH-001` is ready/running as appropriate;
- downstream fan-out is not ready before `GRAPH-001` passes;
- `DATA-001`, `RESEARCH-001`, and `EVIDENCE-001` become ready after `GRAPH-001` passes;
- `GHIDRA-001` stays blocked until `DATA-001` passes.

## 20.6 Explicit exclusions

Do not implement in `GRAPH-001`:

- automatic Claude session launching;
- Git worktree creation;
- agent scheduling;
- agent teams;
- background orchestration;
- MCP;
- emulation;
- AI reasoning;
- Ghidra changes;
- evidence-model changes;
- synthetic firmware changes.

# 21. DATA-001 - synthetic firmware laboratory

## Goal

Create controlled binary fixtures with hidden ground truth.

Required fixture categories:

1. temperature threshold controller;
2. RPM-like calculation;
3. one-dimensional lookup table;
4. two-dimensional lookup table;
5. state machine;
6. multi-function call graph;
7. integer/bit-mask manipulation;
8. timer-like counter logic.

For every fixture preserve:

- source;
- compiler identity;
- compiler flags;
- target architecture;
- unstripped build;
- stripped build;
- expected functions;
- expected constants;
- expected relationships;
- expected behavior.

The analysis agent must never receive source or ground truth during evaluation.

Current known issue from pre-graph work: only six of the eight required fixture categories exist, and some behavior fixtures are tied to x86-64 macOS/Mach-O. `DATA-001` owns the decision to keep, extend, or make the fixture target more portable.

# 22. RESEARCH-001 - select first ECU architecture

Research candidate processor/ECU families using:

- processor documentation quality;
- Ghidra support;
- emulator availability;
- instruction-set complexity;
- peripheral complexity;
- public technical material;
- availability of legally usable examples;
- reverse-engineering community support;
- commercial relevance;
- availability of domain experts.

Outputs:

```text
docs/research/ecu-target-matrix.md
docs/research/ecu-target-matrix.csv
```

Columns should include:

```text
ECU family
manufacturer
approximate era
processor
architecture
endianness
firmware size range
processor documentation
Ghidra support
emulator availability
peripheral difficulty
sample-data availability
commercial relevance
estimated difficulty
notes
```

Research recommends candidates. A human gate chooses the target.

# 23. EVIDENCE-001 - epistemic data model

Implement the first SQLite evidence model.

Initial entities:

```text
Binary
Function
MemoryRegion
Hypothesis
Evidence
Relationship
```

Hypothesis fields should support:

```text
id
binary_id
subject
claim
status
confidence
created_at
updated_at
```

Suggested statuses:

```text
UNTESTED
SUPPORTED
WEAKENED
REJECTED
CONFIRMED
```

Every hypothesis change must preserve history. Do not silently overwrite previous belief state.

Relationships should support:

```text
subject
predicate
object
confidence
evidence references
```

Current known pre-graph gaps include missing `Evidence`/`Relationship` entities, no complete status model, and insufficient hypothesis history.

# 24. GHIDRA-001 - deterministic static analysis

Dependencies:

```text
REPO-001
DATA-001
```

Do not add an LLM.

Required operations:

```text
analyze_binary
list_memory_regions
list_functions
get_function
decompile_function
get_callers
get_callees
get_cross_references
list_strings
search_constant
read_bytes
```

Create internal Python models such as:

```text
BinaryAnalysis
MemoryRegion
FunctionRecord
DecompilerResult
CrossReference
```

Raw Ghidra/Java objects must not leak into the rest of the application.

Analysis results must serialize to JSON.

CLI target:

```bash
ecu-recovery analyze <binary>
```

Expected output categories:

- binary metadata;
- memory map;
- function count;
- function records;
- call relationships;
- analysis warnings.

Current known pre-graph gap: the existing analysis path does not yet expose the required analysis-warnings field.

# 25. EVAL-STATIC-001 - hidden-ground-truth evaluation

Dependencies:

```text
DATA-001
GHIDRA-001
```

At minimum measure:

```text
binary import success
function discovery precision
function discovery recall
function start-address accuracy
call-edge precision
call-edge recall
constant discovery
analysis crash rate
serialization success
```

Initial controlled-fixture gate targets:

| Metric | Initial target |
|---|---:|
| Binary import success | 100% |
| Serialization success | 100% |
| Function discovery recall | >= 95% |
| Function discovery precision | >= 95% |
| Call-edge recall | >= 90% |
| Unexpected crashes | 0 |

These are starting thresholds. If baseline measurements show a threshold is poorly chosen, record the observed baseline, reason, proposed threshold change, and human approval. Do not silently lower gates.

Artifacts:

```text
artifacts/evals/static-results.json
artifacts/evals/static-report.md
```

# 26. TOOLS-001 - bounded agent-facing analysis tools

Dependency:

```text
EVAL-STATIC-001
```

Canonical as of 2026-08-17. An earlier revision of this section named
`GHIDRA-001`, which conflicted with Appendix A. The resolution is
`EVAL-STATIC-001` alone: deterministic analysis must be *measured* before it is
exposed through the agent-facing tool layer, and `EVAL-STATIC-001` already
depends on `GHIDRA-001`, so a direct edge would be redundant.

Initial tools:

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

Every tool must have:

- name;
- description;
- input schema;
- output schema;
- validation;
- bounded output size;
- structured error response.

Do not give the future analysis agent arbitrary shell, arbitrary Python, unrestricted filesystem access, or network access as a substitute for proper tools.

# 27. INTEGRATION-STATIC-001

Run an end-to-end deterministic flow:

```text
synthetic stripped binary
  -> Ghidra analysis
  -> internal models
  -> bounded tool layer
  -> evidence persistence
  -> evaluation
```

No LLM is required in this node.

Report:

- successful steps;
- failed steps;
- performance;
- warnings;
- interface mismatches;
- open blockers.

# 28. GATE-STATIC-MVP

The static MVP gate passes only when all required properties are verified.

```text
Synthetic fixtures reproducible          PASS
Stripped binaries available              PASS
Ghidra import                            PASS
Function extraction                      PASS
Call extraction                          PASS
Structured serialization                 PASS
Static evaluation executes               PASS
Function-quality thresholds              PASS
Call-graph threshold                     PASS
Agent-facing tool schemas                PASS
Evidence persistence                     PASS
Full regression suite                    PASS
```

If the gate fails, identify the failing upstream node and create a repair path. Do not continue into AI-agent work.

# 29. Why AI comes after the static gate

Before deterministic retrieval is measurable, introducing an LLM creates ambiguity about the source of an error.

```text
Ghidra?
parser?
tool layer?
context?
prompt?
model?
```

First make the information pipeline measurable. Then add reasoning.

# 30. Phase 2 - investigator agent

Only after `GATE-STATIC-MVP` passes, add:

```text
AGENT-001
HYPOTHESIS-001
EVAL-AGENT-001
REPORT-001
GATE-AGENT-MVP
```

The first agent task is not "reverse engineer the ECU." It is:

> Investigate one function and produce one structured hypothesis.

Suggested schema:

```text
InvestigationHypothesis

id
binary_id
function_id
claim
category
status
confidence
supporting_evidence[]
contradicting_evidence[]
uncertainties[]
alternatives[]
next_questions[]
```

The agent must explicitly distinguish:

```text
KNOWN
INFERRED
UNKNOWN
```

# 31. Agent evaluation

Measure:

- correct function classification;
- unsupported factual claims;
- evidence validity;
- confidence calibration;
- alternative-hypothesis quality;
- recognition of unknowns;
- tool-call errors.

Initial hard targets on controlled benchmarks:

```text
Evidence references valid      = 100%
Schema compliance              = 100%
Unsupported factual claims     <= 5%
Tool hallucinations            = 0
Critical unsupported claims    = 0
```

Semantic classification accuracy should be baselined before selecting a gate threshold.

# 32. Phase 3 - emulation

Only after `GATE-AGENT-MVP`.

First objective:

> Execute known machine code reproducibly.

Not:

> Emulate a complete ECU.

Abstract emulator interface:

```text
load_binary
map_memory
read_memory
write_memory
read_register
write_register
start
stop
step
set_breakpoint
trace_execution
```

The rest of the application should not depend directly on Unicorn, QEMU, or any specific emulator.

Emulation gate requires:

- known machine code executes;
- known output matches expected result;
- registers and memory are inspectable;
- runs are reproducible;
- traces can be captured;
- timeouts work;
- crashes are isolated;
- emulator assumptions are documented.

# 33. Phase 4 - peripheral modeling

Start with the minimum peripherals required by the selected target.

Potential abstractions:

```text
Timer
ADC
GPIO
Serial
PWM
```

Synthetic automotive inputs can later include:

```text
RPM-like pulse input
temperature ADC
throttle ADC
```

Do not attempt a complete vehicle model.

# 34. Phase 5 - experiment engine

Experiment schema:

```text
Experiment

id
hypothesis_id
question
initial_state
input_changes
breakpoints
observation_targets
execution_limits
result
```

Example:

```text
Question:
Does RAM 0x0244 represent engine RPM?

Run A:
pulse frequency representing 1000 RPM

Run B:
pulse frequency representing 3000 RPM

Observe:
RAM 0x0244
executed functions
timer state
table accesses
```

AI may propose an experiment. Deterministic software validates and executes it.

```text
Hypothesis
   -> experiment proposal
   -> deterministic validator
   -> human approval when required
   -> executor
   -> observation
   -> evidence
   -> belief update
```

# 35. Phase 6 - selected C reconstruction

Start with one meaningful function, not an entire ECU.

```text
Static evidence
   +
Dynamic evidence
   |
   v
Reconstruction agent
   |
   v
Candidate C
   |
   v
Compiler
   |
   v
Behavioral comparison
```

Original and candidate receive identical generated inputs.

Measure:

- tests run;
- exact matches;
- mismatches;
- crashes;
- edge-case failures;
- behavioral-equivalence score.

Behavior matters more than textual similarity to hypothetical original source.

# 36. Phase 7 - first authorized historical ECU

Only after the required gates:

```text
GATE-STATIC-MVP
GATE-AGENT-MVP
GATE-EMULATION
GATE-EXPERIMENTATION
GATE-RECONSTRUCTION
SECURITY REVIEW
AUTHORIZED FIRMWARE
HUMAN APPROVAL
```

First real ECU goal:

> Produce useful engineering understanding for five significant firmware functions.

Success does not require whole-firmware reconstruction.

Success means:

- important regions identified;
- meaningful functions investigated;
- evidence-backed hypotheses produced;
- uncertainty explicit;
- incorrect hypotheses measurable;
- expert can inspect evidence;
- expert reports time saved.

# 37. Runtime product roles

Create separate roles only when tools, authority, or context genuinely differ.

## Static Analyst

Uses Ghidra, disassembly, decompiler, xrefs, call graph, and memory layout.

## Dynamic Analyst

Uses emulator state, registers, RAM, traces, and peripheral state.

## Hypothesis Agent

Produces claim, supporting evidence, contradicting evidence, confidence, unknowns, and next test.

## Experiment Planner

Proposes controlled experiments.

## Experiment Executor

Prefer deterministic software. It does not perform open-ended reasoning.

## Reconstruction Agent

Produces candidate C only when enough evidence exists.

## Verification Engine

Runs original behavior and candidate behavior against controlled inputs.

## Critic

Attempts to disprove conclusions by seeking counterexamples, unsupported assumptions, missing branches, untested ranges, and conflicting evidence.

# 38. Context engineering

Never place the entire investigation into every model context.

Separate four layers.

## Raw artifacts

```text
disassembly
decompiler output
execution traces
experiment logs
```

## Persistent knowledge

```text
functions
variables
tables
relationships
hypotheses
evidence
```

## Current working context

Only information required for the current node/task.

## Validated summary

A compact representation of high-confidence findings.

The runtime investigation graph decides what context a node receives.

# 39. Evidence model example

```text
HYPOTHESIS H-104

SUBJECT
FUN_923A

CLAIM
Possible engine-speed calculation.

STATUS
SUPPORTED

CONFIDENCE
0.88

SUPPORTING EVIDENCE
E-014: called from timer-related routine
E-021: reads timer capture register
E-037: output changes with simulated pulse frequency

CONTRADICTING EVIDENCE
none currently

UNKNOWN
exact scaling formula

NEXT TEST
sweep pulse frequency over expected operating range
```

No important AI conclusion should exist without traceable evidence.

# 40. Security and safety boundary

Initial operating boundary:

- legally obtained and authorized firmware only;
- offline or isolated analysis where practical;
- raw firmware treated as untrusted input;
- generated code sandboxed;
- no arbitrary network access for execution environments;
- no arbitrary host execution;
- no firmware flashing;
- no live vehicle control;
- no immobilizer bypass;
- no credential/key extraction;
- no destructive ECU operations.

Security controls to add as required:

- file-size limits;
- path validation;
- timeouts;
- CPU limits;
- memory limits;
- read-only raw firmware storage;
- allowlisted tools;
- sandboxed compiler execution;
- audit logs.

Analysis output is engineering assistance, not certification.

# 41. Human authority

Human engineers remain able to:

- approve/reject hypotheses;
- correct architecture selection;
- provide datasheets;
- label functions/variables;
- inspect raw evidence;
- approve or reject experiments;
- override confidence;
- approve reconstruction;
- export findings.

Human gates are especially important for:

- first architecture selection;
- real firmware introduction;
- safety-boundary changes;
- experiment autonomy changes;
- real customer pilots;
- deployment decisions.

# 42. Evaluation ladder

Every major phase needs an evaluation layer.

## Static analysis

Measure function discovery, addresses, call graph, constants, tables, import stability, and serialization.

## Agent reasoning

Measure classification, evidence correctness, unsupported claims, confidence calibration, unknown recognition, and tool behavior.

## Dynamic analysis

Measure reproducibility, state correctness, trace correctness, timeouts, and crash isolation.

## Reconstruction

Measure behavioral equivalence, edge cases, compiler success, and failure rate.

## Commercial

Measure:

- manual investigation time;
- AI-assisted investigation time;
- time to first useful finding;
- accepted conclusions;
- rejected conclusions;
- expert intervention;
- cost per analysis.

Primary business metric:

> Expert engineering time saved while maintaining trust.

Initial aspirational target: reduce a bounded investigation task by at least 50%. Do not claim this until measured with real specialists.

# 43. Customer pilot design

When technically ready:

1. Find one ECU/embedded specialist.
2. Obtain one authorized firmware problem.
3. Observe and measure the normal workflow.
4. Run the same bounded task with the product.
5. Record useful findings and mistakes.
6. Record time to first useful finding.
7. Record expert interventions.
8. Ask whether they would use it again.
9. Ask what output they would pay for.
10. Use evidence from the pilot to change the product graph.

Potential later business models include engineering-analysis service, per-firmware analysis, professional desktop license, team license, enterprise platform, or software plus expert service. Do not lock pricing before customer evidence.

# 44. Learning track

Learn while building. Do not pause the project for months of theory.

## Agent engineering

Study:

- Andrew Ng / DeepLearning.AI Agentic AI;
- Anthropic long-running agent/harness articles;
- Claude Code worktree and parallel-agent documentation;
- current coding-agent evaluation research.

Focus on tools, planning, context engineering, evals, error analysis, persistent state, and reliable handoffs.

## C

Learn enough to be comfortable with:

```text
pointers
arrays
structs
integer widths
bit operations
memory
function pointers
volatile
embedded C
```

## Assembly

Go deep only for the selected first architecture:

```text
registers
stack
calls/returns
branches
flags
interrupts
addressing
memory-mapped I/O
```

## Reverse engineering

Learn:

```text
disassembly
decompilation
function boundaries
cross references
control flow
data flow
calling conventions
symbol stripping
memory maps
```

Primary hands-on system: Ghidra.

## Embedded systems

Understand microcontrollers, ROM/RAM, interrupts, timers, ADC, PWM, UART/SPI, memory-mapped peripherals, and watchdogs.

## Automotive

As the target becomes real, learn ECU basics, crank/cam signals, RPM, throttle, coolant, fuel control, ignition, CAN/LIN/K-Line, diagnostics, and calibration maps.

## Emulation

Learn CPU state, memory maps, hooks, execution tracing, peripheral abstraction, and firmware rehosting using synthetic binaries first.

# 45. Research and decision discipline

`RESEARCH.md` should record important external ideas using:

```text
source
date
claim
why it matters
decision affected
confidence
```

`DECISIONS.md` should use lightweight architecture decision records.

Example:

```text
ADR-001

Decision:
Use Python as the orchestration language.

Reason:
Strong integration with AI tooling, PyGhidra, data analysis,
evaluation, and emulation libraries.

Alternative:
C++ orchestration.

Why rejected initially:
Higher development friction without a measured performance need.

Revisit when:
Measurements show Python orchestration is a bottleneck.
```

# 46. Graph review after every major gate

Ask:

```text
Which nodes were too large?
Which nodes were unnecessary?
Which tasks should become deterministic code?
Which tasks should be parallelized?
Which agents collided?
Which handoffs lost context?
Which verification was weak?
Where did humans intervene?
What new gate is required?
```

The graph is allowed to change based on evidence.

# 47. Technical victory ladder

## Victory 1 - static structural recovery

Take a C program whose source is known to the benchmark builder, compile it, strip symbols, hide source from the analysis system, run the binary through Ghidra programmatically, and recover structural information against hidden ground truth.

```text
binary
  -> Ghidra
  -> functions
  -> call graph
  -> constants
  -> decompilation
  -> ground-truth evaluation
```

## Victory 2 - evidence-backed explanation

Give the AI controlled Ghidra tools and have it correctly explain five functions with traceable evidence.

## Victory 3 - controlled semantic experiment

Let the agent test one hypothesis by manipulating a controlled emulator input and observe whether the predicted state change occurs.

## Victory 4 - verified C reconstruction

Generate C for one function and compare it behaviorally with the original over a large generated input set.

# 48. Product and startup readiness definitions

## Interesting technology

The project becomes technically interesting when this works reliably:

```text
binary
  -> agent investigation
  -> evidence-backed hypothesis
  -> controlled experiment
  -> belief update
```

## Potential product

A real specialist uses the system on an authorized task and it saves meaningful time while preserving trust.

## Potential startup

Look for repeated signals such as:

- specialists use it repeatedly;
- customers bring their own firmware;
- users ask to use it again;
- analysis saves expensive hours;
- customers refer other customers;
- someone pays;
- one vertical shows repeatable workflows;
- the system improves as evidence accumulates.

# 49. Stop conditions

Pause and reassess if evidence shows:

- every ECU requires near-total custom engineering;
- emulator/peripheral modeling cost dominates value;
- AI static analysis adds little over existing tools;
- experts consistently distrust the evidence model;
- useful authorized firmware is unavailable;
- no meaningful expert time is saved;
- customer frequency is too low;
- existing commercial tools already solve the core pain point.

Do not continue merely because the project is technically hard.

# 50. Immediate execution runbook

Current state:

```text
SPEC-001  PASSED
REPO-001  PASSED
GRAPH-001 READY
```

Do this next:

```text
1. Save this file as docs/MASTER_SPEC.md in the repository.
2. Commit the approved REPO-001 changes if they are still uncommitted.
3. Assign GRAPH-001 to one coding-agent session.
4. Do not run DATA-001, RESEARCH-001, or EVIDENCE-001 yet.
5. Review GRAPH-001's tests and handoff.
6. Mark GRAPH-001 PASSED only when its acceptance conditions pass.
7. Then open up to three isolated worktrees for:
      DATA-001
      RESEARCH-001
      EVIDENCE-001
8. Re-verify pre-graph code against each node contract instead of grandfathering it in.
9. Do not add the investigator agent before GATE-STATIC-MVP.
10. Do not add emulation before GATE-AGENT-MVP.
11. Do not move to real firmware until the real-firmware gate and authorization conditions are satisfied.
```

# 51. Standard instruction to coding agents

Use this as the standing preamble for node execution:

```text
You are executing one node of a dependency-graph engineering project.

Authoritative specification:
docs/MASTER_SPEC.md

Rules:
- Execute only the node I explicitly assign.
- Do not work ahead.
- Respect dependencies and file ownership.
- Existing code is candidate implementation, not proof of completion.
- Run the node's acceptance tests.
- Preserve all previously passing regression obligations.
- Prefer deterministic verification over model judgment.
- Do not self-approve human gates.
- Report ambiguity instead of inventing architecture.
- Return a structured node handoff.
- Stop after the assigned node reaches a terminal/verification state.
```

# 52. Final project rules

For development:

> No downstream node without verified upstream dependencies.

For AI conclusions:

> No important claim without traceable evidence.

For experiments:

> No uncontrolled execution.

For reconstruction:

> No success claim without behavioral verification.

For real firmware:

> No use without authorization and the required human gates.

For graph engineering:

> Keep the graph only while measurements show it improves reliability and coordination.

# 53. Long-term vision

The long-term product is not simply an "AI decompiler for cars."

It is:

> An evidence-driven AI engineering environment for recovering understanding from undocumented embedded software.

Automotive ECUs are the first vertical.

The system should investigate, record what it knows, distinguish inference from fact, design controlled tests, gather evidence, revise incorrect beliefs, reconstruct selected behavior, and verify that reconstruction.

The engineer remains able to inspect why the system believes what it believes.

# Appendix A - GRAPH-001 coding-agent work order

```text
NODE: GRAPH-001
TITLE: Development Graph Infrastructure

DEPENDENCIES
SPEC-001 = PASSED
REPO-001 = PASSED

GOAL
Implement the minimum infrastructure required to represent, validate,
and inspect the development dependency DAG.

DO NOT build a full autonomous agent orchestrator.

OWNERSHIP
ecu-project.graph.yaml
graph/**
prompts/**
artifacts/**
tests/graph/**
TODO.md (minimal status update only)
ARCHITECTURE.md (minimal architecture update only)

REQUIRED GRAPH
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

REQUIRED NODE FIELDS
id
title
depends_on
status
worker
prompt
allowed_paths
verification
retry_budget

VALID STATES
PENDING
READY
RUNNING
VERIFYING
PASSED
FAILED
BLOCKED
NEEDS_HUMAN
UNVERIFIED-UNDER-GRAPH

REQUIRED BEHAVIOR
- list nodes
- inspect dependencies
- validate acyclicity
- validate dependency references
- compute READY frontier
- list PASSED/BLOCKED nodes
- compute what becomes READY after a node passes

VALIDATOR MUST REJECT
- cycles
- duplicate IDs
- unknown dependencies
- invalid states
- self-dependencies

REQUIRED TESTS
- valid graph loads
- cycle rejected
- unknown dependency rejected
- self-dependency rejected
- invalid status rejected
- SPEC-001 and REPO-001 are PASSED
- GRAPH-001 is READY/RUNNING as appropriate
- fan-out not READY before GRAPH-001 passes
- DATA/RESEARCH/EVIDENCE become READY after GRAPH-001 passes
- GHIDRA remains blocked until DATA passes

REGRESSION
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy

DO NOT IMPLEMENT
automatic Claude launching
worktree creation
agent scheduling
agent teams
background orchestration
MCP
emulation
AI reasoning
Ghidra changes
evidence-model changes
synthetic-firmware changes

STOP
After GRAPH-001 verification, stop. Do not start downstream nodes.
```

# Appendix B - first fan-out node prompts

## DATA-001

```text
NODE: DATA-001

Build the controlled synthetic firmware laboratory defined in MASTER_SPEC.md.
Treat existing pre-graph fixtures as candidate implementation.
Audit them against all eight required fixture categories.
Implement only missing/incorrect requirements.
Preserve source, stripped/unstripped binaries, compiler metadata,
ground truth, expected relationships, and behavior.
Do not add AI or Ghidra functionality.
Run all existing regressions plus fixture-specific tests.
Return structured handoff and stop.
```

## RESEARCH-001

```text
NODE: RESEARCH-001

Research and rank candidate legacy ECU/processor families for the first
authorized real-world experiment using the target matrix defined in
MASTER_SPEC.md.

Use primary technical sources where possible.
Do not obtain questionable proprietary firmware.
Do not make the final target decision; that is a human gate.
Produce ecu-target-matrix.md and ecu-target-matrix.csv.
Return structured handoff and stop.
```

## EVIDENCE-001

```text
NODE: EVIDENCE-001

Audit the existing evidence persistence code against MASTER_SPEC.md.
Treat it as candidate implementation.
Implement the required Binary, Function, MemoryRegion, Hypothesis,
Evidence, and Relationship models, status behavior, migrations, and
hypothesis history without silently overwriting prior belief state.
Do not add LLM logic.
Run regressions and evidence-specific tests.
Return structured handoff and stop.
```

# Appendix C - research references

1. DeepLearning.AI. *Agentic AI*. Instructor: Andrew Ng. https://www.deeplearning.ai/courses/agentic-ai
2. Anthropic Engineering. *Effective harnesses for long-running agents*. https://www.anthropic.com/engineering
3. Anthropic Engineering. *Harness design for long-running application development*. https://www.anthropic.com/engineering
4. Anthropic Engineering. *Scaling Managed Agents: Decoupling the brain from the hands*. https://www.anthropic.com/engineering/managed-agents
5. Claude Code Docs. *Run parallel sessions with worktrees*. https://code.claude.com/docs/en/worktrees
6. Claude Code Docs. *Run agents in parallel*. https://code.claude.com/docs/en/agents
7. Anthropic Engineering. *Building a C compiler with a team of parallel Claudes*. https://www.anthropic.com/engineering/building-c-compiler
8. Li, H. et al. *LoopsBench: From Harness Engineering to Loop Engineering in Coding Agent Evaluation*. arXiv:2608.00267, 2026. https://arxiv.org/abs/2608.00267
9. *AgentFlow: Building Agent Dependency Graphs for Static Analysis of Agent Programs*. arXiv:2607.01640, 2026. https://arxiv.org/abs/2607.01640
10. *Repository Intelligence Graph: Deterministic Architectural Map for LLM Code Assistants*. arXiv:2601.10112, 2026. https://arxiv.org/abs/2601.10112
11. Karpathy, A. *Software Is Changing (Again)*. AI Startup School, 2025. https://www.youtube.com/watch?v=LCEmiRjPEtQ
