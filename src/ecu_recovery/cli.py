"""Command-line entry point for the first static-analysis vertical slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import AnalysisError, ArchitectureConfig, to_storage_record
from .doctor import render_doctor_report, run_doctor
from .ghidra.bridge import load_functions
from .intake import IntakeError, profile_binary
from .report import write_markdown
from .store import InvestigationStore


class GraphUnavailableError(RuntimeError):
    """The development-graph package or its graph file could not be located."""


def _render_development_graph(graph_file: Path | None, command: str) -> str:
    """Load the development graph and render the requested view.

    `graph/` is development scaffolding that lives beside `src/`, not inside the
    installed package, so it is imported lazily and only when this subcommand
    runs. That keeps `ecu_recovery` free of a hard dependency on the machinery
    used to build it: an installed copy of the product still works with no
    graph package present.
    """
    from .doctor import find_project_root

    root = find_project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        import graph as development_graph
    except ImportError as error:
        raise GraphUnavailableError(
            f"development graph package not importable from {root}: {error}"
        ) from error
    loaded = development_graph.load_graph(graph_file or (root / "ecu-project.graph.yaml"))
    if command == "ready":
        return development_graph.render_ready(loaded)
    return development_graph.render_status_table(loaded)


def run_graph(args: argparse.Namespace) -> int:
    """Render the development graph. Read-only: it never edits node status."""
    print(_render_development_graph(args.graph_file, args.graph_command))
    return 0


def _parse_optional_address(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value, 0)
    except ValueError as error:
        raise ValueError(f"could not parse address {value!r}") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecu-recovery")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="check the local development environment")
    doctor.add_argument(
        "--project-root",
        type=Path,
        help="repository root to inspect (defaults to the nearest pyproject.toml)",
    )
    graph_parser = subparsers.add_parser("graph", help="inspect the development graph")
    graph_commands = graph_parser.add_subparsers(dest="graph_command", required=True)
    for name, description in (
        ("status", "show every development node and its status"),
        ("ready", "list only nodes whose dependencies have all passed"),
    ):
        command = graph_commands.add_parser(name, help=description)
        command.add_argument(
            "--graph-file",
            type=Path,
            help="graph definition to read (defaults to ecu-project.graph.yaml)",
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
    analyze.add_argument(
        "--ghidra",
        action="store_true",
        help="run Ghidra static analysis through PyGhidra",
    )
    analyze.add_argument(
        "--language",
        help="Ghidra language id, e.g. x86:LE:64:default (detected when omitted)",
    )
    analyze.add_argument("--compiler-spec", help="Ghidra compiler spec id")
    analyze.add_argument(
        "--base-address",
        help="load address for a raw dump that carries none, e.g. 0x8000",
    )
    analyze.add_argument(
        "--decompile",
        action="store_true",
        help="include decompiler output for every function (slow)",
    )
    analyze.add_argument(
        "--analysis-json",
        default="artifacts/analysis.json",
        help="where to write the serialized static-analysis result",
    )
    return parser


def run_ghidra_analysis(
    args: argparse.Namespace, store: InvestigationStore, analysis_id: int
) -> str:
    """Analyze the firmware with Ghidra, persist functions, and export JSON."""
    from .analysis.ghidra import GhidraEngine

    architecture = ArchitectureConfig(
        language_id=args.language,
        compiler_spec_id=args.compiler_spec,
        base_address=_parse_optional_address(args.base_address),
        processor_label=args.processor,
    )
    engine = GhidraEngine()
    with engine.analyze_binary(args.firmware, architecture) as session:
        export = session.export(include_decompilation=args.decompile)
        decompiled = {item.function_id: item for item in export.decompilations}
        for function in export.functions:
            result = decompiled.get(function.id)
            store.save_function(
                analysis_id,
                to_storage_record(function, result.text if result and result.success else None),
            )
    destination = Path(args.analysis_json)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(export.as_dict(), indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(f"engine={export.program.engine} {export.program.engine_version}")
    print(f"language={export.program.language_id}")
    print(f"functions={len(export.functions)}")
    print(f"analysis_json={destination}")
    return str(destination)


def run_analyze(args: argparse.Namespace) -> int:
    profile = profile_binary(args.firmware, processor=args.processor, byte_order=args.byte_order)
    store = InvestigationStore(args.database)
    analysis_id = store.save_profile(profile)
    if args.ghidra_export:
        for function in load_functions(args.ghidra_export):
            store.save_function(analysis_id, function)
    if args.ghidra:
        run_ghidra_analysis(args, store, analysis_id)
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
        if args.command == "graph":
            return run_graph(args)
        if args.command == "analyze":
            return run_analyze(args)
    except (AnalysisError, GraphUnavailableError, IntakeError, OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
