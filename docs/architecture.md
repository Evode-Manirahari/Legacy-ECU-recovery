# Architecture

## Scope

MVP 1 supports one investigator-selected processor family and static analysis.
Architecture auto-detection, emulation, peripheral simulation, reconstruction,
and vehicle interaction are later milestones.

For the authoritative description of implemented components, see the root
[`ARCHITECTURE.md`](../ARCHITECTURE.md). This file records design constraints for
the analysis path.

## Data flow

```text
firmware bytes ──> safe intake ──> immutable profile ──> SQLite
                                         │                 │
Ghidra (out of process) ──> JSON adapter ─┘                 ├──> report
                                                           └──> future agent tools
```

The intake component reads an allow-listed firmware file as bytes. It never
executes, imports, or shells out through the image. Ghidra runs separately and
crosses a validated JSON boundary. This keeps model access narrow and auditable.

## Trust model

- Facts from deterministic tools are stored as `known` only when directly
  observable.
- Semantic labels are hypotheses with confidence, evidence, and uncertainty.
- Missing processor or byte-order information stays `unknown`.
- The model provider must remain replaceable; domain records contain no
  provider-specific types.
- Firmware and derived artifacts stay local by default.

## Near-term tool surface

The first agent-facing API should expose small read operations: list functions,
get a function, get callers/callees, read a bounded ROM range, find constants,
and record a hypothesis. Rename/comment mutations should require an explicit
investigator action and be kept in the analysis database before Ghidra is changed.
