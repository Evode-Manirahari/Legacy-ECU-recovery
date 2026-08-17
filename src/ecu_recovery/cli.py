"""Command-line entry point for the first static-analysis vertical slice."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .doctor import render_doctor_report, run_doctor
from .ghidra.bridge import load_functions
from .intake import IntakeError, profile_binary
from .report import write_markdown
from .store import InvestigationStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecu-recovery")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="check the local development environment")
    doctor.add_argument(
        "--project-root",
        type=Path,
        help="repository root to inspect (defaults to the nearest pyproject.toml)",
    )
    analyze = subparsers.add_parser("analyze", help="profile a firmware image without executing it")
    analyze.add_argument("firmware")
    analyze.add_argument(
        "--processor", help="explicit processor/model selected by the investigator"
    )
    analyze.add_argument("--byte-order", choices=("big", "little"))
    analyze.add_argument(
        "--ghidra-export", help="validated JSON export produced by a Ghidra script"
    )
    analyze.add_argument("--database", default="artifacts/investigations.sqlite3")
    analyze.add_argument("--report", default="artifacts/report.md")
    return parser


def run_analyze(args: argparse.Namespace) -> int:
    profile = profile_binary(args.firmware, processor=args.processor, byte_order=args.byte_order)
    store = InvestigationStore(args.database)
    analysis_id = store.save_profile(profile)
    if args.ghidra_export:
        for function in load_functions(args.ghidra_export):
            store.save_function(analysis_id, function)
    report = write_markdown(store, analysis_id, args.report)
    print(f"analysis_id={analysis_id}")
    print(f"sha256={profile.sha256}")
    print(f"report={report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            report = run_doctor(args.project_root)
            print(render_doctor_report(report))
            return 0 if report.successful else 1
        if args.command == "analyze":
            return run_analyze(args)
    except (IntakeError, OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
