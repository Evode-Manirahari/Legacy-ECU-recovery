# NODE: EVIDENCE-001

**Title:** Epistemic evidence data model
**Depends on:** `GRAPH-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Implement the first SQLite evidence model.

## Ownership

Allowed: `src/ecu_recovery/evidence/**`, `tests/evidence/**`.

Forbidden: `src/ecu_recovery/analysis/**`, `samples/**`, `graph/**`.

## Required entities

```text
Binary
Function
MemoryRegion
Hypothesis
Evidence
Relationship
```

Hypothesis fields: `id`, `binary_id`, `subject`, `claim`, `status`,
`confidence`, `created_at`, `updated_at`.

Hypothesis statuses: `UNTESTED`, `SUPPORTED`, `WEAKENED`, `REJECTED`,
`CONFIRMED`.

Relationships support subject, predicate, object, confidence, and evidence
references.

## Central requirement

Every hypothesis change must preserve history. Never silently overwrite
previous belief state — the ability to show that the system changed its mind,
and why, is the point of this model.

## Candidate implementation to audit

Pre-graph code persists analyses, functions, and hypotheses but has no
`Evidence` or `Relationship` entity, no status model, and no hypothesis
history; it overwrites on conflict. Treat it as candidate implementation.

## Deliverables

Entities, status behaviour, migrations, preserved history, and tests.

## Acceptance

```bash
uv run pytest
```

All existing regressions must keep passing.

## Exclusions

Do not implement LLM logic.

## Stop

Return the structured handoff and stop.
