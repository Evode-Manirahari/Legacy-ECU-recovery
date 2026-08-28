"""Score frozen transcripts and write the recorded artifacts.

    uv run python -m ecu_recovery.evaluation.agent

Exit status reflects the *machinery* checks only. A zero here does not mean the
agent is good and does not authorize `GATE-AGENT-MVP`: on authored transcripts
it means the scoring detects what it claims to detect. The report says so above
the numbers, and so does this.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import DetectionStatus
from .report import render_report
from .runner import evaluate

DEFAULT_TRANSCRIPTS = Path("tests/evaluation/agent/transcripts")
DEFAULT_OUTPUT = Path("artifacts/evals/agent")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ecu_recovery.evaluation.agent")
    parser.add_argument("--transcripts", type=Path, default=DEFAULT_TRANSCRIPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--samples-root", type=Path)
    args = parser.parse_args(argv)

    run = evaluate(args.transcripts, args.samples_root)
    args.output.mkdir(parents=True, exist_ok=True)
    results = args.output / "agent-results.json"
    report = args.output / "agent-report.md"
    results.write_text(json.dumps(run.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(render_report(run), encoding="utf-8")

    for check in run.gate:
        print(
            f"{'PASS' if check.passed else 'FAIL'}  {check.metric:34} "
            f"{check.render_target():>8}  {check.render_observed()}"
        )
    print(f"adversarial_corpus={run.adversarial}")
    print(f"detector_verification={run.detection_status.value}")
    for mismatch in run.detection_mismatches:
        print(f"  mismatch: {mismatch}")
    print(f"gate_would_pass={run.gate_passed}")
    print(f"provenance={run.provenance.kind}")
    print(
        "sufficient_for_GATE-AGENT-MVP="
        f"{run.gate_passed and not run.baseline_only and not run.adversarial}"
    )
    print(f"results={results}")
    print(f"report={report}")
    # Over an adversarial corpus the gate is expected to fail, so success means
    # the scorer found exactly what was planted. Over a clean corpus it means
    # the gate held.
    #
    # NOT_APPLICABLE is not success. A corpus can only be adversarial if some
    # transcript declares planted defects, so reaching this branch with nothing
    # in scope means the declaring transcripts were all excluded - a state worth
    # a non-zero exit rather than a quiet zero. Written out rather than left to
    # the truthiness of a tri-state.
    succeeded = run.detection_status is DetectionStatus.PASS if run.adversarial else run.gate_passed
    return 0 if succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
