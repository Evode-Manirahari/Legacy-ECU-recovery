# Architecture Decisions

Decisions are append-only. If a choice changes, add a superseding entry instead
of rewriting history.

Entries from `ADR-001` onward use the master specification's record format:
decision, reason, alternative, why rejected, revisit when. Entries above that
line predate the graph process and are kept verbatim as history.

---

# Part 1 — Numbered decisions (current format)

## ADR-001 — Adopt `docs/MASTER_SPEC.md` as the authoritative specification

**Date:** 2026-08-17
**Status:** accepted

**Decision:**
The master graph specification governs this project. The earlier linear
"Prompt 0…22" document is deprecated and must not be executed independently.
Where any document conflicts with the master specification, the master
specification wins.

**Reason:**
Two competing process documents produce contradictory acceptance criteria and
untraceable node status. One authority removes that ambiguity.

**Alternative:**
Continue the linear prompt sequence and treat the graph as commentary.

**Why rejected:**
The linear sequence advances on "the previous prompt finished," whereas the graph
advances only on verified prerequisites. The weaker rule cannot supervise the
stronger one.

**Revisit when:**
Measurements show the graph overhead exceeds its benefit. The graph is an
engineering hypothesis, not doctrine.

## ADR-002 — Treat pre-graph code as `UNVERIFIED-UNDER-GRAPH`

**Date:** 2026-08-17
**Status:** accepted

**Decision:**
Code produced under the deprecated sequence is not retroactively marked `PASSED`
for the graph nodes it resembles. It is recorded as `UNVERIFIED-UNDER-GRAPH`
until a human decides its status or the node is re-run under its contract.

**Reason:**
A graph edge means the prerequisite has been *verified*, not that an agent
reported done. Silently importing prior work as `PASSED` would make the first
gate meaningless — and the gap table in `ARCHITECTURE.md` shows real divergence,
including two missing `DATA-001` fixture categories and an absent
`EVIDENCE-001` relationship model.

**Alternative:**
Declare `REPO-001`, `DATA-001`, and `GHIDRA-001` passed on inspection.

**Why rejected:**
Their master-specification acceptance criteria were never evaluated. Declaring
them passed would assert a measurement that was never taken.

**Revisit when:**
A human assigns node status, or each node is re-run and verified.

## ADR-003 — Keep documentation-only nodes free of application code

**Date:** 2026-08-17
**Status:** accepted

**Decision:**
`SPEC-001` modifies documentation only. No file under `src/`, `tests/`,
`scripts/`, or `samples/` is touched, and no dependency or configuration changes.

**Reason:**
The node contract forbids implementing application code, and mixing a
documentation reconciliation with behavior changes destroys the ability to
attribute a later regression.

**Alternative:**
Fix the identified gaps while the context is fresh.

**Why rejected:**
Those gaps belong to `DATA-001`, `EVIDENCE-001`, and `GHIDRA-001`. Working ahead
violates the graph and skips their verification.

**Revisit when:**
Never for this node. Each gap is closed by its owning node.

---

## ADR-004 — Select MPC5xx / 32-bit big-endian PowerPC as the first target architecture

**Date:** 2026-08-18
**Status:** accepted (human gate)

**Decision:**
The first real-world target architecture is MPC5xx, 32-bit big-endian PowerPC.
`RESEARCH-001` recommended candidates; this entry records the human selection
that its contract reserved. SH-2 remains the second candidate and TriCore
remains a later, commercially important target.

This authorizes architecture selection only. It does not authorize obtaining
proprietary firmware, working on real vehicle hardware, flashing, or emulation
before its own phase.

**Reason:**
Genuine legacy automotive relevance, mature Ghidra support, a practical GCC
toolchain, and working QEMU and Unicorn paths for later behavioural validation.
Emulator availability was the sharpest divider in the candidate matrix, and it
decides whether `EMU-001` is one problem or two. MPC5xx is also a plausible
route to symbolic execution later, and is difficult enough to test the product
thesis without being the hardest thing available.

**Alternative:**
SH-2, which has the best public reverse-engineering material of any candidate;
or TriCore, which has the highest commercial relevance.

**Why rejected:**
SH-2 has no usable emulator - neither Unicorn nor QEMU covers bare-metal SH-2 -
so choosing it would mean solving behavioural validation separately. TriCore
combines protected flash, high peripheral complexity, partly-NDA documentation,
and no emulator: four research problems at once, which is the wrong shape for a
first experiment. Both remain ranked candidates rather than discarded ones.

**Revisit when:**
A legally held MPC5xx example proves unobtainable, the toolchain turns out not
to reproduce period-representative binaries, or measurement shows the
architecture is not exercising the parts of the thesis it was chosen to test.

# Part 2 — Historical entries (pre-graph process)

These entries predate `ADR-001`. They are retained unedited. Their technical
content stands; their references to numbered "Prompts" describe the deprecated
sequence and should be read as history.

## 2026-08-17 — Begin with evidence-backed understanding

**Status:** accepted

The product begins with binary understanding, not flashing, vehicle control, or
whole-firmware reconstruction. Semantic conclusions must retain confidence,
evidence, and uncertainty.

## 2026-08-17 — Use Python for orchestration

**Status:** accepted

Python 3.11+ provides a practical interface to analysis tools and supports fast
experimentation. Performance-sensitive emulation may use another language later,
but that need has not been demonstrated.

## 2026-08-17 — Use synthetic ground truth before real ECU firmware

**Status:** accepted

Known-source samples allow objective comparison of discovered functions,
constants, call relationships, and behavior. The source will be stored separately
from artifacts made available to the investigator.

## 2026-08-17 — Select one architecture explicitly

**Status:** accepted

Automatic architecture detection is deferred. The first architecture will be
chosen using toolchain availability, Ghidra support, emulation prospects,
documentation, legal sample availability, and access to expert validation.

## 2026-08-17 — Keep reverse-engineering internals behind plain models

**Status:** accepted

Ghidra-specific Java objects must not escape the analysis adapter. Core and agent
layers will consume serializable Python records so analysis engines and model
providers remain replaceable.

## 2026-08-17 — Use SQLite for early investigation state

**Status:** provisional

SQLite is sufficient for a local, single-investigator prototype and requires no
service. Revisit only after concurrency or scale creates a measured limitation.

## 2026-08-17 — Lock the Python environment with uv

**Status:** accepted

The repository uses standard `pyproject.toml` metadata and commits `uv.lock` for
repeatable local and automated installations. Ruff owns linting and formatting;
mypy runs in strict mode; pytest runs the test suite. Runtime code remains free
of third-party dependencies in Prompt 1.

## 2026-08-17 — Treat Ghidra and Java as optional during scaffolding

**Status:** accepted

The doctor command detects both dependencies but returns success with a clear
warning when either is unavailable. Prompt 3 may strengthen these checks after
Ghidra becomes an implemented execution path.

## 2026-08-17 — Use x86-64 Mach-O for synthetic dataset v1

**Status:** accepted for the laboratory only

The first fixtures target little-endian `x86_64-apple-darwin`. The current host
can build, strip, inspect, and execute this target without an unpinned external
cross-toolchain. Ghidra and Unicorn both support x86-64. This does not select the
eventual legacy ECU family or processor; that remains gated on authorized real
samples, documentation, tool support, emulator feasibility, and expert input.

## 2026-08-17 — Separate evaluation truth from investigator input

**Status:** accepted

The investigator receives only `firmware.stripped`. Source, JSON ground truth,
symbols-on binaries, callable behavior libraries, and build records are evaluator
assets. Symbols-on and stripped executables originate from the same compiled file
so expected functions can be matched by exact start address after a blinded run.

## 2026-08-17 — Use PyGhidra in process rather than headless scripts

**Status:** accepted

Ghidra is reached through PyGhidra's JVM bridge instead of shelling out to
`analyzeHeadless` with an export script. In-process access gives the decompiler,
reference manager, and listing directly, which the later agent tool layer needs
for interactive queries; a headless script would force every new capability
through a batch export round trip.

The cost is that Ghidra parses untrusted binaries inside our process. That is
acceptable while the only inputs are fixtures this repository compiled, and it
must be revisited before real firmware arrives. `ecu_recovery.ghidra.bridge`
remains for importing an analysis produced elsewhere.

## 2026-08-17 — Make a function's entry address its identity

**Status:** accepted

`FunctionRecord.id` is the zero-padded hex entry address. Names do not survive
stripping and Ghidra's `FUN_*` labels are display artifacts that change when a
user renames a function, so neither can be an identifier. Entry address is stable
across renames, matches the ground-truth scoring rule in `docs/synthetic-lab.md`,
and lets an id be used anywhere an address is accepted.

## 2026-08-17 — Put response bounds on the interface, not in the engine

**Status:** accepted

`MAX_READ_BYTES`, `MAX_INSTRUCTIONS`, `MAX_RESULTS`, and the shared validators
live in `analysis/base.py`. An agent must never be able to request an unbounded
response, and a limit that lives inside one engine is a limit the next engine
silently loses. Prompt 4's tool layer builds on these rather than inventing its
own.

## 2026-08-17 — Report decompiler failure as data

**Status:** accepted

`decompile_function` returns `DecompilerResult(success=False, warnings=...)`
instead of raising. Which functions the decompiler cannot handle is itself an
investigative finding the agent must be able to reason about and cite, and an
exception would discard it.

## 2026-08-17 — Treat PyGhidra as an optional extra

**Status:** accepted

`pyghidra` installs via `uv sync --extra ghidra`, not as a core dependency. The
analysis models, interface, bounds, and serialization stay testable on a host
with no Ghidra and no JVM, which keeps the adapter boundary honest. Ghidra tests
carry the `ghidra` marker and skip with a stated reason when it is absent.

**Supersedes** the Prompt 1 note that Prompt 3 might make Ghidra mandatory.

## 2026-08-17 — Require an application root for Ghidra discovery

**Status:** accepted

Discovery looks for `Ghidra/application.properties` under `GHIDRA_INSTALL_DIR`,
`GHIDRA_HOME`, known Homebrew and `/opt` locations, or a directory reachable from
a launcher on `PATH`. The previous check accepted any executable named
`ghidraRun`, which could pass while PyGhidra still had nothing to start.

## 2026-08-17 — Widen the intake extension allowlist

**Status:** accepted

The allowlist now covers `.bin`, `.rom`, `.img`, `.hex`, `.s19`, `.srec`, and the
laboratory's `.stripped` and `.symbols`. The previous three-extension list
rejected this project's own investigator-visible artifact. The extension check is
a guard against selecting the wrong file, not a security control; extension-free
raw dumps are a known gap recorded in `TODO.md`.
