# NODE: DETECTION-SCOPE-001

**Title:** Detector verification scope
**Depends on:** `PROVENANCE-001`
**Verification:** commands
**Retry budget:** 2

## Why this node exists

`verify_detection` compares a transcript's complete detector vector against the
complete expectation the fixture declares, and reports
`"<id>: fixture declares no detector expectations"` when there is none. That is
right for a fixture: an omission there is a fixture bug, and comparing only the
fields a fixture happened to mention would catch a missed defect and never an
invented one.

It is wrong for a captured transcript. Nothing was planted in a real call, so
there is nothing to declare, and every one of the eight baseline transcripts
will trip it. Reproduced before this node was written, on a corpus whose single
transcript carried a verified capture record:

```text
provenance=model
detector_verification=FAIL
  mismatch: baseline-01: fixture declares no detector expectations
```

and in the report that certifies the baseline:

```text
- detector verification: FAIL

### Detector disagreed with what the fixtures planted
- baseline-01: fixture declares no detector expectations
```

A genuine sample, described as a defective fixture, under a heading saying the
detector disagreed with something nobody planted.

**It fails no gate invariant, and that is the reason to fix it now rather than
later.** A false FAIL standing beside real PASSes teaches whoever reads the
first baseline that the line carries no information — and that same line is how
a genuine detector regression would announce itself. `BASELINE-AGENT-001` freezes
what it captures, so repairing this afterwards would mean re-scoring a frozen
run to change what its report says.

**The second half is subtler and is also this node.** A corpus with nothing
planted cannot be detector-verified at all. Reporting `PASS` over zero checks is
the same class of claim as `FAIL` over zero checks: a status asserted where
nothing was measured. Silencing the false FAIL by letting it read PASS would
replace a visible wrong answer with an invisible one.

## Goal

```text
scope derived from verified capture linkage -> in-scope transcripts verified -> status, or an honest absence of one
```

## Ownership

Allowed:

- `src/ecu_recovery/evaluation/agent/scoring.py`
- `src/ecu_recovery/evaluation/agent/runner.py`
- `src/ecu_recovery/evaluation/agent/models.py`
- `src/ecu_recovery/evaluation/agent/report.py`
- `src/ecu_recovery/evaluation/agent/__main__.py`
- `tests/evaluation/agent/**`

Files, not trees, and one file per reason: scope is decided in `scoring.py`,
applied in `runner.py`, represented in `models.py`, and rendered in `report.py`
and `__main__.py`. All are `EVAL-AGENT-001` slices; `runner.py` and the test
tree are also `PROVENANCE-001`'s. Every overlap is the ordered kind — this node
is directly downstream of `PROVENANCE-001` and transitively downstream of
`EVAL-AGENT-001` — so it can never run beside either.

Forbidden, and load-bearing:

- `artifacts/evals/agent/**`. Every fixture in the authored corpus declares its
  expectations, so scope there is universal and the status stays `PASS`. The
  committed results and report must therefore not move **at all**, and a node
  that could rewrite them could not be held to that. This is the same control
  `PROVENANCE-001` was given, and for the same reason.
- `src/ecu_recovery/evaluation/agent/captures.py` and `transcripts.py`. This
  node reads verified linkage; it does not get to redefine it.
- `src/ecu_recovery/evaluation/agent/gate.py` and `adjudication.py`. No
  threshold, no metric, no adjudication.
- `src/ecu_recovery/agent/**` and `src/ecu_recovery/providers/**`.
- `artifacts/agent-baseline/**`.

## Fixed decisions

- **Scope is derived from verified capture linkage, never from
  `transcript.provenance`.** A transcript that exempts itself from detector
  verification by calling itself a capture would hand back, in a new place,
  exactly what #42 closed. The exemption must rest on the same check that
  decides run provenance: a record that exists, recomputes its own identifier,
  names that transcript, and matches its call record.
- **An authored fixture with no expectations stays a mismatch.** That behaviour
  is correct and is not what this node is repairing.
- **A status over zero checks is not a status.** When no transcript was in
  scope, the run reports that plainly rather than `PASS` or `FAIL`.
- **The authored corpus artifacts stay byte-identical.** Whatever representation
  the tri-state takes must leave `detection_verified` reading exactly as it does
  today for a corpus where scope is universal.
- **No API call.** Every test uses frozen JSON, as the whole evaluator does.

## Required properties

1. **A verified captured transcript is out of scope**, and produces no mismatch
   and no heading about fixtures.
2. **A transcript claiming `"provenance": "model"` without a verified capture is
   still in scope**, and still reports its missing expectations. Self-declared
   provenance buys no exemption.
3. **An authored fixture missing its expectations is still a mismatch**, and a
   fixture whose declared vector disagrees with the scorer still fails.
4. **A corpus with nothing in scope reports no status** — not `PASS`, not
   `FAIL` — in the JSON, in the report, and on the command line, and says how
   many transcripts were out of scope and why.
5. **A mixed corpus verifies the fixtures it contains** and reports the captured
   transcripts as out of scope.
6. **Exit status stays meaningful.** The adversarial branch already turns on
   `expects` being present, so an out-of-scope corpus cannot reach it; make that
   explicit rather than incidental.
7. **Nothing else moves.** `GATE_TARGETS` untouched, metrics untouched, and the
   committed authored-corpus results and report reproduce byte for byte.

## Required regressions

- a verified capture produces no detector mismatch;
- a transcript claiming model provenance with **no** capture record still
  reports its missing expectations — the adversarial case, and the one that
  matters most;
- a transcript whose capture record was edited, swapped, or is missing is
  likewise still in scope;
- an authored fixture with no `expects` is still a mismatch;
- an authored fixture whose declared vector is wrong still fails;
- a corpus entirely of verified captures reports no status rather than `PASS`;
- a mixed corpus verifies the fixtures and exempts the captures;
- the authored corpus reproduces its committed results and report byte for byte.

## Acceptance

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Plus: re-scoring the authored corpus reproduces the committed artifacts with no
diff.

## Exclusions

Do not make an OpenAI API call. Do not capture, write, or commit a baseline
transcript. Do not start `BASELINE-AGENT-001`, `REVIEW-AGENT-BASELINE-001`, or
`GATE-AGENT-MVP`. Do not change thresholds, metrics, adjudication, or the
capture and linkage machinery. Do not widen this node's ownership: if the repair
cannot be done inside these files, stop and report it as an authorization
finding.

## Stop

Return the structured handoff and stop.
