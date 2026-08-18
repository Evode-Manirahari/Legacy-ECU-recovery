"""Render an evaluation run as Markdown.

Every percentage in this report is printed beside the counts it came from. That
is not decoration: a gate decision that cannot be recomputed from the page is
not reviewable, and EVALS.md requires the raw counts with every rate.
"""

from __future__ import annotations

from .models import EVIDENCE_CLASSES, SCHEMA_VERSION, EvaluationRun, FixtureResult, render_address


def _fixture_section(fixture: FixtureResult) -> list[str]:
    lines = [f"### `{fixture.sample_id}`", ""]
    if fixture.functions is None or fixture.call_edges is None:
        lines += [
            f"- imported: {fixture.imported}",
            f"- serialized: {fixture.serialized}",
            f"- unexpected crash: {fixture.crashed}",
            f"- failure: {fixture.failure}",
            "",
        ]
        return lines

    region = ", ".join(
        f"`{item.name}` {render_address(item.start_address)}-{render_address(item.end_address)}"
        for item in fixture.scoring_region
    )
    functions, edges = fixture.functions, fixture.call_edges
    lines += [
        f"Scoring region: {region or 'none'}",
        f"Analysis digest: `{fixture.analysis_digest[:16]}`",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Function discovery recall | {functions.recall.render()} |",
        f"| Function discovery precision | {functions.precision.render()} |",
        f"| Function start-address accuracy | {functions.start_address_accuracy.render()} |",
        f"| Call-edge recall | {edges.recall.render()} |",
        f"| Call-edge precision | {edges.precision.render()} |",
        "",
        f"Reported outside the scoring region: {len(functions.reported_out_of_scope)} function(s)"
        " — compiler or runtime startup code, listed rather than counted as false positives.",
        "",
    ]
    if functions.missed:
        lines += [
            "Missed functions: " + ", ".join(render_address(item) for item in functions.missed),
            "",
        ]
    if functions.false_positives:
        lines += [
            "False positives: "
            + ", ".join(render_address(item) for item in functions.false_positives),
            "",
        ]
    if edges.missed:
        lines += [
            "Missed call edges: "
            + ", ".join(f"{render_address(a)}->{render_address(b)}" for a, b in edges.missed),
            "",
        ]
    if fixture.constants is not None:
        constants = fixture.constants
        lines += [
            f"Constant evidence — recovered {constants.recovered.render()}:",
            "",
            "| Value | Evidence | Recovered | Detail |",
            "|---|---|---|---|",
        ]
        for entry in constants.entries:
            lines.append(
                f"| {entry.value} | `{entry.evidence}` | "
                f"{'yes' if entry.recovered else 'no'} | {entry.detail} |"
            )
        lines.append("")
    if fixture.analysis_warnings:
        lines += ["Analysis warnings:", ""]
        lines += [
            f"- `{code}` ({severity}) x{count}"
            for code, severity, count in fixture.analysis_warnings
        ]
        lines.append("")
    return lines


def render_report(run: EvaluationRun) -> str:
    environment = run.environment
    aggregate = run.aggregate
    verdict = "PASS" if run.gate_passed else "FAIL"
    lines = [
        "# Static analysis evaluation — hidden ground truth",
        "",
        f"**Gate: {verdict}**",
        "",
        "Produced by `EVAL-STATIC-001`. Every fixture was analyzed from",
        "`firmware.stripped` alone; the result was serialized and digested before",
        "the answer key was opened, and the digest was re-checked after scoring.",
        "",
        "This report measures the deterministic static-analysis layer. It says",
        "nothing about semantic understanding, which no part of this node evaluates.",
        "",
        "## Environment",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Engine | {environment.engine} {environment.engine_version} |",
        f"| PyGhidra | {environment.pyghidra_version} |",
        f"| Python | {environment.python_version} |",
        f"| Platform | {environment.platform_system} {environment.platform_machine} |",
        f"| Analysis schema | {environment.analyzer_schema_version} |",
        f"| Results schema | {SCHEMA_VERSION} |",
        "",
        "No timestamp is recorded. The artifact is byte-reproducible on a given",
        "host so a later run can be diffed against it; the commit carrying it is",
        "the record of when it was taken.",
        "",
        "## Gate",
        "",
        "| Metric | Target | Observed | Result |",
        "|---|---|---|---|",
    ]
    for check in run.gate:
        lines.append(
            f"| {check.metric} | {check.render_target()} | {check.render_observed()} | "
            f"{'PASS' if check.passed else 'FAIL'} |"
        )
    lines += [
        "",
        "## Aggregate",
        "",
        "Micro-averaged: counts are pooled across fixtures, not averaged as rates,",
        "so a three-function fixture does not outweigh a six-function one.",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Binary import success | {aggregate.binary_import.render()} |",
        f"| Serialization success | {aggregate.serialization.render()} |",
        f"| Function discovery recall | {aggregate.function_recall.render()} |",
        f"| Function discovery precision | {aggregate.function_precision.render()} |",
        f"| Function start-address accuracy | {aggregate.start_address_accuracy.render()} |",
        f"| Call-edge recall | {aggregate.call_edge_recall.render()} |",
        f"| Call-edge precision | {aggregate.call_edge_precision.render()} |",
        f"| Unexpected analysis crashes | {aggregate.unexpected_crashes} |",
        f"| Functions reported outside scoring regions | "
        f"{aggregate.reported_out_of_scope_functions} |",
        "",
        "## Constant evidence — reported, not gated",
        "",
        f"Recovered under the semantic rule: {aggregate.constants_recovered.render()}.",
        "",
        "A declared constant the compiler never emitted is a property of the",
        "fixture, not a failure of the analyzer, so this is not a threshold. Raw",
        "matching bytes are not evidence and are not counted anywhere below.",
        "",
        "| Evidence class | Count | Counts as recovery |",
        "|---|---:|---|",
    ]
    recovery_note = {
        "operand": "yes — an instruction operand carries the value",
        "referenced-data": "yes — a data object code refers to holds the value",
        "reachable-table-data": "no — reachable via read_bytes, named by nothing",
        "unsupported": "no — the compiler emitted no evidence at all",
    }
    for name in EVIDENCE_CLASSES:
        lines.append(
            f"| `{name}` | {aggregate.constants_by_evidence.get(name, 0)} | {recovery_note[name]} |"
        )
    lines += ["", "## Per fixture", ""]
    for fixture in run.fixtures:
        lines += _fixture_section(fixture)
    return "\n".join(lines).rstrip() + "\n"
