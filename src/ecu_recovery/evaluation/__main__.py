"""Run the evaluation and write the two recorded artifacts.

A module entry point rather than an `ecu-recovery` subcommand: the CLI lives in
`src/ecu_recovery/cli.py`, which is outside this node's ownership. Wiring a
subcommand is a one-line follow-up for whoever owns that file.

    uv run python -m ecu_recovery.evaluation

Exit status is the gate: zero when every threshold passes, one when any fails,
so a later pipeline can depend on it without parsing the report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .harness import run_evaluation
from .report import render_report

DEFAULT_OUTPUT = Path("artifacts/evals")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ecu_recovery.evaluation")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="directory for static-results.json and static-report.md",
    )
    parser.add_argument(
        "--samples-root",
        type=Path,
        help="fixture corpus root (defaults to samples/synthetic)",
    )
    parser.add_argument(
        "--sample",
        action="append",
        dest="samples",
        help="score only this fixture; repeatable",
    )
    args = parser.parse_args(argv)

    run = run_evaluation(sample_ids=args.samples, samples_root=args.samples_root)
    args.output.mkdir(parents=True, exist_ok=True)
    results = args.output / "static-results.json"
    report = args.output / "static-report.md"
    results.write_text(json.dumps(run.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(render_report(run), encoding="utf-8")

    for check in run.gate:
        print(
            f"{'PASS' if check.passed else 'FAIL'}  {check.metric:32} "
            f"{check.render_target():>8}  {check.render_observed()}"
        )
    print(f"gate={'PASS' if run.gate_passed else 'FAIL'}")
    print(f"results={results}")
    print(f"report={report}")
    return 0 if run.gate_passed else 1


if __name__ == "__main__":
    sys.exit(main())
