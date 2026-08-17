# NODE: RESEARCH-001

**Title:** First ECU architecture research
**Depends on:** `GRAPH-001`
**Verification:** human
**Retry budget:** 2

## Goal

Research and rank candidate legacy ECU/processor families for the first
authorized real-world experiment.

Recommend candidates. Do not make the final choice; target selection is a human
gate.

## Ownership

Allowed: `docs/research/**`.

Forbidden: everything else.

## Evaluation criteria

Processor documentation quality, Ghidra support, emulator availability,
instruction-set complexity, peripheral complexity, public technical material,
availability of legally usable examples, reverse-engineering community support,
commercial relevance, and availability of domain experts.

## Deliverables

```text
docs/research/ecu-target-matrix.md
docs/research/ecu-target-matrix.csv
```

Columns: ECU family, manufacturer, approximate era, processor, architecture,
endianness, firmware size range, processor documentation, Ghidra support,
emulator availability, peripheral difficulty, sample-data availability,
commercial relevance, estimated difficulty, notes.

Use primary technical sources where possible and record them.

## Acceptance

Human review. An agent must not self-approve this node.

## Exclusions

Do not obtain questionable proprietary firmware. Do not download firmware of
uncertain provenance into this repository. Do not make the final target
decision.

## Stop

Return the structured handoff and stop.
