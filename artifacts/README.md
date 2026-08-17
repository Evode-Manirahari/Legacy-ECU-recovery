# Artifacts

Generated outputs produced by graph nodes. Nothing here is hand-written, and
nothing here is a source of truth — every file is reproducible by re-running
the node that owns it.

Expected contents as nodes execute:

| Path | Produced by |
|---|---|
| `evals/static-results.json` | `EVAL-STATIC-001` |
| `evals/static-report.md` | `EVAL-STATIC-001` |
| `integration/static-integration-report.md` | `INTEGRATION-STATIC-001` |

Local scratch output from `ecu-recovery analyze` also lands here by default
(`artifacts/investigations.sqlite3`, `artifacts/report.md`,
`artifacts/analysis.json`).

Failure data is kept, not deleted. Failed experiments, wrong hypotheses,
compiler errors, tool failures, and rejected reconstruction candidates are
evidence about the system's behaviour and belong in the record.
