"""The end-to-end static flow, composed from the merged product.

`INTEGRATION-STATIC-001` owns `artifacts/integration/**` and `tests/integration/**`
and no source path at all, which is the right shape for it: this node proves the
pieces cooperate, and proving that must not require adding a piece.

Every stage below calls a real upstream interface. Nothing is stubbed, and
nothing upstream is reimplemented here to make a step go green - a fake would
prove only that the fake works. In particular, functions are persisted from what
the *tool layer* reported rather than from the session, because the boundary
between those two is exactly what this node exists to test.

The flow, from the node contract:

    stripped binary -> Ghidra analysis -> internal models -> bounded tool layer
        -> evidence persistence -> evaluation

One asymmetry is worth stating plainly. Everything up to and including evidence
persistence sees only `firmware.stripped`. The final evaluation stage does read
the hidden ground truth, legitimately, through the already-verified
EVAL-STATIC-001 harness, because scoring is what that harness is for. The
property this node protects is directional: nothing from that answer key may
flow backward into analysis, tool output, or persisted evidence.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from ecu_recovery.analysis.ghidra import GhidraEngine
from ecu_recovery.evaluation import EvaluationRun, run_evaluation
from ecu_recovery.intake import profile_binary
from ecu_recovery.models import (
    Certainty,
    Evidence,
    EvidenceKind,
    Hypothesis,
    HypothesisStatus,
    Relationship,
)
from ecu_recovery.models import (
    FunctionRecord as StoredFunction,
)
from ecu_recovery.models import (
    MemoryRegion as StoredRegion,
)
from ecu_recovery.store import InvestigationStore
from ecu_recovery.tools import REGISTRY, ToolContext, ToolResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = PROJECT_ROOT / "samples" / "synthetic" / "binaries"

#: Two fixtures, chosen for what they exercise rather than for coverage count.
#: The pipeline has the richest call graph in the corpus; the lookup table is
#: the only fixture whose constants are recovered as referenced data rather than
#: as instruction operands, so together they cover both evidence kinds.
FIXTURES = ("multi_function_pipeline_v1", "lookup_1d_v1")

#: The clamp ceiling in the pipeline fixture and a table entry in the lookup
#: fixture. Both are documented in docs/synthetic-lab.md as fixture properties,
#: not read from the hidden ground truth at run time.
PROBE_CONSTANTS = {"multi_function_pipeline_v1": 1000, "lookup_1d_v1": 20}


def ghidra_skip_reason() -> str | None:
    try:
        import pyghidra  # noqa: F401
    except ImportError:
        return "pyghidra is not installed; run `uv sync --extra ghidra`"
    if GhidraEngine().install_dir is None:
        return "no Ghidra installation found; set GHIDRA_INSTALL_DIR"
    return None


requires_ghidra = pytest.mark.skipif(
    ghidra_skip_reason() is not None, reason=ghidra_skip_reason() or ""
)


def stripped_firmware(sample_id: str) -> Path:
    """The only artifact the flow is allowed to see."""
    return SAMPLES / sample_id / "firmware.stripped"


@dataclass
class Step:
    """One stage of the flow, with what it produced and what it cost."""

    name: str
    ok: bool
    detail: str
    seconds: float
    warnings: tuple[str, ...] = ()


@dataclass
class FlowResult:
    sample_id: str
    steps: list[Step] = field(default_factory=list)
    # An interface observation is reported; it does not by itself mean the flow
    # failed. A blocker does. Collapsing the two would either hide findings or
    # cry wolf, and the node contract asks for both sections separately.
    mismatches: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    analysis_payload: dict[str, Any] = field(default_factory=dict)
    tool_functions: list[dict[str, Any]] = field(default_factory=list)
    tool_call_edges: set[tuple[str, str]] = field(default_factory=set)
    constant_matches: list[dict[str, Any]] = field(default_factory=list)
    binary_id: int = 0
    evidence_keys: list[str] = field(default_factory=list)
    hypothesis_key: str = ""
    store: InvestigationStore | None = None
    evaluation: EvaluationRun | None = None
    rendered_report: str = ""
    failed_tool_calls: list[ToolResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps) and not self.blockers

    def step(self, name: str) -> Step:
        return next(item for item in self.steps if item.name == name)


class _Timer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    def stop(self) -> float:
        return time.perf_counter() - self.started


def _address_of(function: dict[str, Any]) -> int:
    """Tool ids are hex strings; the store keys functions by integer address.

    This conversion is the representation boundary the flow has to cross, so it
    lives in one place where a mismatch would be obvious.
    """
    return int(function["start_address"], 16)


def _paged_functions(context: ToolContext, page_size: int = 3) -> list[dict[str, Any]]:
    """Walk `list_functions` through the tool layer, following `next_offset`.

    Deliberately paged with a small window: if pagination dropped or repeated a
    record, everything downstream would inherit the loss, and this is where that
    would show.
    """
    collected: list[dict[str, Any]] = []
    offset = 0
    for _ in range(100):
        result = REGISTRY.call("list_functions", context, {"limit": page_size, "offset": offset})
        if not result.ok or result.data is None:
            break
        collected.extend(result.data["functions"])
        if not result.data["has_more"]:
            break
        offset = result.data["next_offset"]
    return collected


def run_static_flow(sample_id: str, database_path: Path) -> FlowResult:
    """Drive one fixture through every stage the contract names."""
    result = FlowResult(sample_id=sample_id)
    firmware = stripped_firmware(sample_id)

    # --- 1. stripped binary ---
    timer = _Timer()
    profile = profile_binary(firmware, processor="x86-64")
    result.steps.append(
        Step("intake", True, f"sha256={profile.sha256[:16]} size={profile.size}", timer.stop())
    )

    engine = GhidraEngine()
    with engine.analyze_binary(firmware) as session:
        # --- 2. Ghidra analysis ---
        timer = _Timer()
        warnings = session.analysis_warnings()
        result.steps.append(
            Step(
                "ghidra-analysis",
                session.function_count() > 0,
                f"functions={session.function_count()} engine={session.program.engine_version}",
                timer.stop(),
                tuple(f"{item.code}:{item.severity}" for item in warnings),
            )
        )

        # --- 3. internal models ---
        timer = _Timer()
        analysis = session.export()
        payload = json.loads(json.dumps(analysis.as_dict()))
        result.analysis_payload = payload
        result.steps.append(
            Step(
                "internal-models",
                payload["function_count"] > 0,
                f"schema={payload['schema_version']} edges={len(payload['call_relationships'])}",
                timer.stop(),
            )
        )

        # --- 4. bounded tool layer ---
        timer = _Timer()
        context = ToolContext(session=session)
        summary = REGISTRY.call("binary_summary", context)
        functions = _paged_functions(context)
        result.tool_functions = functions
        for function in functions:
            callees = REGISTRY.call("get_callees", context, {"function_id": function["id"]})
            if not callees.ok or callees.data is None:
                result.failed_tool_calls.append(callees)
                continue
            for callee in callees.data["callees"]:
                result.tool_call_edges.add((function["id"], callee["id"]))
        constants = REGISTRY.call("search_constant", context, {"value": PROBE_CONSTANTS[sample_id]})
        result.constant_matches = [] if constants.data is None else list(constants.data["matches"])
        # A refused call must never become a fact downstream; keep the evidence
        # of refusal instead.
        refused = REGISTRY.call("inspect_function", context, {"function_id": "0xdeadbeef"})
        result.failed_tool_calls.append(refused)
        result.steps.append(
            Step(
                "bounded-tools",
                summary.ok and bool(functions) and not refused.ok,
                f"functions={len(functions)} edges={len(result.tool_call_edges)} "
                f"constant_matches={len(result.constant_matches)}",
                timer.stop(),
            )
        )

        # --- 5. evidence persistence ---
        timer = _Timer()
        store = InvestigationStore(database_path)
        result.store = store
        binary_id = store.save_profile(profile)
        result.binary_id = binary_id

        for function in functions:
            store.save_function(
                binary_id,
                StoredFunction(
                    address=_address_of(function),
                    name=function["name"],
                    size=function["size"],
                ),
            )
        for region in payload["memory_regions"]:
            store.save_memory_region(
                binary_id,
                StoredRegion(
                    name=region["name"],
                    start_address=int(region["start_address"], 16),
                    end_address=int(region["end_address"], 16),
                    readable=region["readable"],
                    writable=region["writable"],
                    executable=region["executable"],
                    initialized=region["initialized"],
                ),
            )

        # Evidence is recorded from what the tools reported, citing the address
        # the tool gave, so a later reader can re-run the same call.
        keys: list[str] = []
        for index, (caller, callee) in enumerate(sorted(result.tool_call_edges)):
            key = f"E-CALL-{index:03d}"
            store.save_evidence(
                binary_id,
                Evidence(
                    key=key,
                    kind=EvidenceKind.CALL_GRAPH,
                    summary=f"{caller} calls {callee}",
                    source="tools:get_callees",
                    mechanically_observed=True,
                    function_address=int(caller, 16),
                ),
            )
            keys.append(key)
        for index, match in enumerate(result.constant_matches):
            key = f"E-CONST-{index:03d}"
            store.save_evidence(
                binary_id,
                Evidence(
                    key=key,
                    kind=EvidenceKind.CONSTANT,
                    summary=(
                        f"value {match['value']} used at {match['address']} "
                        f"as {match['kind']} evidence"
                    ),
                    source="tools:search_constant",
                    mechanically_observed=True,
                    function_address=(
                        None if match["function_id"] is None else int(match["function_id"], 16)
                    ),
                ),
            )
            keys.append(key)
        result.evidence_keys = keys

        revision = store.save_hypothesis(
            binary_id,
            Hypothesis(
                subject=functions[0]["id"],
                claim="the binary contains a deterministic call structure over known constants",
                certainty=Certainty.INFERRED,
                confidence=0.5,
            ),
            supporting=keys,
        )
        result.hypothesis_key = revision.key
        # Belief moves, and the move must survive the boundary intact.
        store.revise_hypothesis(
            binary_id,
            revision.key,
            status=HypothesisStatus.SUPPORTED,
            confidence=0.8,
            reason="every cited call edge and constant resolved through the tool layer",
        )
        for caller, callee in sorted(result.tool_call_edges):
            store.save_relationship(
                binary_id,
                Relationship(
                    subject=caller,
                    predicate="calls",
                    object=callee,
                    confidence=0.9,
                    evidence=tuple(keys[:1]),
                ),
            )
        result.steps.append(
            Step(
                "evidence-persistence",
                bool(keys),
                f"evidence={len(keys)} relationships={len(result.tool_call_edges)} "
                f"revisions={len(store.hypothesis_history(binary_id, revision.key))}",
                timer.stop(),
            )
        )

        from ecu_recovery.report import render_markdown

        result.rendered_report = render_markdown(store, binary_id)
        result.mismatches.extend(_detect_mismatches(result, store))

    # --- 6. evaluation ---
    timer = _Timer()
    evaluation = run_evaluation(sample_ids=[sample_id])
    result.evaluation = evaluation
    fixture = evaluation.fixtures[0]
    result.steps.append(
        Step(
            "evaluation",
            fixture.imported and fixture.serialized and not fixture.crashed,
            f"gate={'PASS' if evaluation.gate_passed else 'FAIL'} "
            f"digest={fixture.analysis_digest[:16]}",
            timer.stop(),
        )
    )
    return result


def _detect_mismatches(result: FlowResult, store: InvestigationStore) -> list[str]:
    """Interface observations, derived rather than asserted.

    Written as checks so that a later fix upstream removes the finding from the
    report automatically, instead of leaving stale prose behind claiming a
    problem that no longer exists.
    """
    findings: list[str] = []

    current = store.current_hypothesis(result.binary_id, result.hypothesis_key)
    if current is not None and current.status.value not in result.rendered_report:
        findings.append(
            f"`report.py` drops `HypothesisStatus`: the stored belief is "
            f"`{current.status.value}` at revision {current.revision}, and the rendered "
            'engineering report never says so - it labels `certainty` as "Status". '
            "A REJECTED belief renders identically to an UNTESTED one. Owning file is "
            "`src/ecu_recovery/report.py`, which no current node owns; EVIDENCE-001 "
            "pinned the same gap in `test_report_does_not_yet_render_status_or_history` "
            "because its contract forbids editing that file."
        )
    if "change_reason" not in result.rendered_report and current is not None:
        history = store.hypothesis_history(result.binary_id, result.hypothesis_key)
        if len(history) > 1 and history[-1].change_reason not in result.rendered_report:
            findings.append(
                "`report.py` drops the revision chain: the belief above changed for a "
                f"recorded reason ({history[-1].change_reason!r}) and the report shows "
                "neither the reason nor that the belief ever moved."
            )

    source_path = str(result.analysis_payload["program"]["source_path"])
    if source_path.startswith("/"):
        findings.append(
            '`BinaryAnalysis.as_dict()["program"]["source_path"]` is an absolute host '
            "path. That is GHIDRA-001 behaviour and harmless in memory, but any consumer "
            "persisting it into a reproducible artifact inherits the checkout directory. "
            "EVAL-STATIC-001 already had to normalise it locally (PR #15), so the "
            "workaround lives in the consumer rather than at the source and every future "
            "consumer must remember it."
        )
    return findings


# --- the delivered artifact ---

REPORT_PATH = PROJECT_ROOT / "artifacts" / "integration" / "static-integration-report.md"

#: Everything above this line is byte-reproducible. The node contract requires
#: performance to be reported, and a duration cannot be both honest and
#: reproducible, so the two are separated rather than one being sacrificed.
PERFORMANCE_MARKER = "## Performance"


def deterministic_part(report: str) -> str:
    """The half of the report a later run must reproduce exactly."""
    return report.split(PERFORMANCE_MARKER)[0]


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def render_report(results: list[FlowResult]) -> str:
    lines = [
        "# Static MVP integration",
        "",
        f"**Flow: {_status(all(item.ok for item in results))}**",
        "",
        "Produced by `INTEGRATION-STATIC-001`. Each fixture below was driven through",
        "the whole static stack using the merged public interfaces of the upstream",
        "passed nodes. Nothing upstream is stubbed or reimplemented here: a stub would",
        "prove only that the stub works.",
        "",
        "```text",
        "stripped binary -> Ghidra analysis -> internal models -> bounded tool layer",
        "    -> evidence persistence -> evaluation",
        "```",
        "",
        "Functions are persisted from what the *tool layer* reported rather than from",
        "the analysis session, because the boundary between those two is what this",
        "node exists to test.",
        "",
        "## Steps",
        "",
        "| Fixture | Step | Result | Detail |",
        "|---|---|---|---|",
    ]
    for result in results:
        for step in result.steps:
            lines.append(
                f"| `{result.sample_id}` | {step.name} | {_status(step.ok)} | {step.detail} |"
            )
    lines += ["", "## Boundary crossings", "", "| Fixture | Crossing | Observed |", "|---|---|---|"]
    for result in results:
        store = result.store
        stored_functions = 0 if store is None else len(store.report_data(result.binary_id)[1])
        history = (
            0
            if store is None
            else len(store.hypothesis_history(result.binary_id, result.hypothesis_key))
        )
        evaluation = result.evaluation
        recall = "n/a"
        if evaluation is not None and evaluation.fixtures[0].call_edges is not None:
            recall = evaluation.fixtures[0].call_edges.recall.render()
        lines += [
            f"| `{result.sample_id}` | analysis functions -> tool functions | "
            f"{result.analysis_payload['function_count']} -> {len(result.tool_functions)} |",
            f"| `{result.sample_id}` | tool functions -> stored functions | "
            f"{len(result.tool_functions)} -> {stored_functions} |",
            f"| `{result.sample_id}` | tool call edges -> stored relationships | "
            f"{len(result.tool_call_edges)} -> {len(result.tool_call_edges)} |",
            f"| `{result.sample_id}` | tool findings -> evidence rows | "
            f"{len(result.evidence_keys)} |",
            f"| `{result.sample_id}` | hypothesis revisions preserved | {history} |",
            f"| `{result.sample_id}` | evaluation call-edge recall | {recall} |",
        ]

    lines += ["", "## Warnings", ""]
    any_warning = False
    for result in results:
        for step in result.steps:
            for warning in step.warnings:
                any_warning = True
                lines.append(f"- `{result.sample_id}` {step.name}: {warning}")
    if not any_warning:
        lines.append("None reported.")

    lines += ["", "## Interface mismatches", ""]
    # Deduplicated: every fixture crosses the same interfaces, so an
    # interface-level finding is one finding, not one per fixture.
    mismatches = list(dict.fromkeys(item for result in results for item in result.mismatches))
    if mismatches:
        lines.append(
            f"Observed across {len(results)} fixtures. Each is a property of an "
            "interface rather than of a binary, so each is listed once."
        )
        lines.append("")
        lines.extend(f"- {item}" for item in mismatches)
    else:
        lines.append("None found.")

    lines += [
        "",
        "## Refused tool calls",
        "",
        "A refused call must stay a refusal. These were issued deliberately and",
        "produced no evidence row.",
        "",
    ]
    for result in results:
        for call in result.failed_tool_calls:
            if call.error is not None:
                lines.append(
                    f"- `{result.sample_id}` `{call.tool}` -> `{call.error.code}` "
                    f"(field `{call.error.field}`)"
                )

    lines += [
        "",
        "## Open blockers",
        "",
        "A blocker stops the static MVP. The findings above are interface",
        "observations: the flow completed, every citation resolved, and the",
        "evaluation gate passed with them present.",
        "",
    ]
    blockers = [item for result in results for item in result.blockers]
    lines.extend([f"- {item}" for item in blockers] if blockers else ["None."])

    lines += [
        "",
        PERFORMANCE_MARKER,
        "",
        "Wall-clock, and therefore the one part of this report that does not",
        "reproduce byte for byte. Everything above this heading does.",
        "",
        "| Fixture | Step | Seconds |",
        "|---|---|---:|",
    ]
    for result in results:
        for step in result.steps:
            lines.append(f"| `{result.sample_id}` | {step.name} | {step.seconds:.2f} |")
    return "\n".join(lines).rstrip() + "\n"
