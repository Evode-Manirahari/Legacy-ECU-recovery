# NODE: SPEC-001

**Title:** Engineering foundation and project contract
**Depends on:** none
**Status:** PASSED (human-approved 2026-08-17)
**Verification:** human
**Retry budget:** 1

## Goal

Establish the project contract, architecture record, decision log, evaluation
policy, threat model, research log, and work queue.

## Ownership

Allowed: `PROJECT.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TODO.md`,
`EVALS.md`, `THREAT_MODEL.md`, `RESEARCH.md`.

Forbidden: all application code.

## Deliverables

- `PROJECT.md` defining problem, target user, initial value proposition,
  initial technical goal, non-goals, and milestones.
- `ARCHITECTURE.md` documenting only systems that exist or are explicitly
  planned.
- `DECISIONS.md` using lightweight ADRs.
- `TODO.md` with NOW, NEXT, and LATER.
- `EVALS.md` stating that correctness is measured against controlled
  ground-truth binaries.
- `THREAT_MODEL.md` defining authorized firmware only, no live vehicle control,
  no firmware flashing, no immobilizer or security-access bypass, no credential
  or key extraction, no arbitrary host execution, and sandboxed generated code.
- `RESEARCH.md`.

## Acceptance

Documentation is internally consistent. Human approval is required because this
node defines project policy; an agent must not self-approve it.

## Exclusions

Do not implement application code.

## Stop

Return the structured handoff and stop.
