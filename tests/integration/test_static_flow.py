"""Does the static stack actually cooperate?

Each upstream node is already verified in isolation, so retesting subsystems
here would prove nothing new. What is untested until now is the seams: whether
an address written by one layer means the same thing to the next, whether a
citation survives persistence, whether paging drops provenance, and whether a
refused tool call can be mistaken for a fact.

Every test below crosses at least one boundary.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from integration_support import (
    FIXTURES,
    REPORT_PATH,
    FlowResult,
    deterministic_part,
    render_report,
    requires_ghidra,
    run_static_flow,
)

from ecu_recovery.models import HypothesisStatus

pytestmark = [pytest.mark.ghidra, requires_ghidra]


@pytest.fixture(scope="module")
def flows(tmp_path_factory: pytest.TempPathFactory) -> Iterator[list[FlowResult]]:
    workspace = tmp_path_factory.mktemp("integration")
    yield [run_static_flow(sample_id, workspace / f"{sample_id}.sqlite3") for sample_id in FIXTURES]


def _by_id(flows: list[FlowResult], sample_id: str) -> FlowResult:
    return next(item for item in flows if item.sample_id == sample_id)


# --- the flow completes ---


def test_every_step_of_the_contract_flow_succeeds(flows: list[FlowResult]) -> None:
    for flow in flows:
        failed = [step.name for step in flow.steps if not step.ok]
        assert failed == [], f"{flow.sample_id}: {failed}"


def test_the_flow_covers_every_stage_the_contract_names(flows: list[FlowResult]) -> None:
    expected = [
        "intake",
        "ghidra-analysis",
        "internal-models",
        "bounded-tools",
        "evidence-persistence",
        "evaluation",
    ]
    for flow in flows:
        assert [step.name for step in flow.steps] == expected


def test_more_than_one_fixture_is_exercised(flows: list[FlowResult]) -> None:
    """One fixture would show the stack works on one binary, not that it works."""
    assert len(flows) >= 2


# --- address and id representation across layers ---


def test_one_address_means_the_same_thing_in_all_three_layers(flows: list[FlowResult]) -> None:
    """Analysis hex, tool id, and stored integer must agree exactly."""
    for flow in flows:
        assert flow.store is not None
        from_analysis = {item["start_address"] for item in flow.analysis_payload["functions"]}
        from_tools = {item["start_address"] for item in flow.tool_functions}
        _, stored_rows, _ = flow.store.report_data(flow.binary_id)
        from_store = {f"0x{int(row['address']):08x}" for row in stored_rows}

        assert from_tools == from_analysis, flow.sample_id
        assert from_store == from_analysis, flow.sample_id


def test_a_tool_function_id_is_the_start_address(flows: list[FlowResult]) -> None:
    for flow in flows:
        for function in flow.tool_functions:
            assert function["id"] == function["start_address"]


def test_call_edges_agree_between_the_models_and_the_tools(flows: list[FlowResult]) -> None:
    """The tools walked the graph one function at a time; the export did it once."""
    for flow in flows:
        from_models = {
            (edge["caller_id"], edge["callee_id"])
            for edge in flow.analysis_payload["call_relationships"]
        }
        assert flow.tool_call_edges == from_models, flow.sample_id


def test_the_evaluation_scores_the_same_edges_the_tools_reported(
    flows: list[FlowResult],
) -> None:
    """Two independent paths to the call graph must not disagree."""
    for flow in flows:
        assert flow.evaluation is not None
        metrics = flow.evaluation.fixtures[0].call_edges
        assert metrics is not None
        scored = {
            (f"0x{caller:08x}", f"0x{callee:08x}") for caller, callee in metrics.true_positives
        }
        assert scored == flow.tool_call_edges, flow.sample_id


# --- pagination must not lose provenance ---


def test_paging_through_the_tools_loses_nothing(flows: list[FlowResult]) -> None:
    """The flow pages three at a time; a dropped or repeated record shows here."""
    for flow in flows:
        ids = [item["id"] for item in flow.tool_functions]
        assert len(ids) == len(set(ids)), f"{flow.sample_id} repeated a function while paging"
        assert len(ids) == flow.analysis_payload["function_count"]


# --- evidence references resolve ---


def test_every_cited_evidence_key_resolves_to_a_stored_observation(
    flows: list[FlowResult],
) -> None:
    for flow in flows:
        assert flow.store is not None
        stored = {item.key for item in flow.store.evidence_for_binary(flow.binary_id)}
        assert set(flow.evidence_keys) <= stored, flow.sample_id
        assert flow.evidence_keys, "a flow that cites nothing proves nothing"


def test_every_evidence_address_resolves_to_a_reported_function(
    flows: list[FlowResult],
) -> None:
    """A citation pointing at nothing is the failure this check exists for."""
    for flow in flows:
        assert flow.store is not None
        reported = {int(item["start_address"], 16) for item in flow.tool_functions}
        for evidence in flow.store.evidence_for_binary(flow.binary_id):
            if evidence.function_address is None:
                continue
            assert evidence.function_address in reported, (
                f"{flow.sample_id}: evidence {evidence.key} cites "
                f"0x{evidence.function_address:08x}, which no tool reported"
            )


def test_the_belief_carries_its_basis_through_persistence(flows: list[FlowResult]) -> None:
    for flow in flows:
        assert flow.store is not None
        current = flow.store.current_hypothesis(flow.binary_id, flow.hypothesis_key)
        assert current is not None
        assert current.evidence, f"{flow.sample_id}: the stored belief cites nothing"


# --- a refused tool call is not a fact ---


def test_a_refused_tool_call_produced_no_evidence(flows: list[FlowResult]) -> None:
    """The failure mode: an error object read as a finding and written down."""
    for flow in flows:
        assert flow.store is not None
        refusals = [item for item in flow.failed_tool_calls if item.error is not None]
        assert refusals, "the flow must actually issue a refused call to test this"
        assert all(item.data is None for item in refusals)

        summaries = " ".join(
            item.summary for item in flow.store.evidence_for_binary(flow.binary_id)
        )
        for refused in refusals:
            assert refused.error is not None
            assert refused.error.code not in summaries
            assert "0xdeadbeef" not in summaries


# --- status and history survive to the report ---


def test_hypothesis_status_and_history_survive_persistence(flows: list[FlowResult]) -> None:
    for flow in flows:
        assert flow.store is not None
        history = flow.store.hypothesis_history(flow.binary_id, flow.hypothesis_key)
        assert [item.revision for item in history] == [1, 2]
        assert history[0].status is HypothesisStatus.UNTESTED
        assert history[1].status is HypothesisStatus.SUPPORTED
        assert history[0].confidence == 0.5
        assert history[1].confidence == 0.8
        assert history[0].created_at == history[1].created_at


def test_the_report_renders_current_belief_not_a_superseded_one(
    flows: list[FlowResult],
) -> None:
    """Revision 2 is what a reader sees; revision 1 is not rendered beside it."""
    for flow in flows:
        assert "Confidence: 80%" in flow.rendered_report
        assert "Confidence: 50%" not in flow.rendered_report
        assert flow.rendered_report.count("deterministic call structure") == 1


# --- no leakage across any boundary ---


def test_nothing_java_shaped_crosses_any_boundary(flows: list[FlowResult]) -> None:
    for flow in flows:
        payload = json.dumps(
            {
                "analysis": flow.analysis_payload,
                "functions": flow.tool_functions,
                "constants": flow.constant_matches,
            }
        )
        assert "ghidra." not in payload
        assert "java." not in payload
        assert "jpype" not in payload.lower()


def test_no_ground_truth_flows_back_into_analysis_tools_or_evidence(
    flows: list[FlowResult],
) -> None:
    """Direction is what matters here, not absence.

    The analysis -> bounded tools -> evidence-persistence path sees only
    `firmware.stripped`. The final evaluation stage does read hidden ground
    truth, legitimately and by design, through the already-verified
    EVAL-STATIC-001 harness in order to score. What must never happen is the
    reverse: ground truth flowing backward into analysis, tool output, or
    persisted evidence. A real symbol name appearing below would be that leak.
    """
    for flow in flows:
        assert flow.store is not None
        names = {item["name"] for item in flow.tool_functions}
        assert all(name.startswith("FUN_") or name == "entry" for name in names), names

        _, stored_rows, _ = flow.store.report_data(flow.binary_id)
        stored_names = {str(row["name"]) for row in stored_rows}
        assert all(name.startswith("FUN_") or name == "entry" for name in stored_names)
        assert "firmware.symbols" not in flow.rendered_report


def test_the_analysis_payload_carries_an_absolute_path_and_the_flow_says_so(
    flows: list[FlowResult],
) -> None:
    """A found interface observation, pinned rather than worked around here.

    `BinaryAnalysis` records where the file was, which is GHIDRA-001 behaviour.
    It matters only when a consumer persists it, so what this node checks is
    that the flow detects it and that it never reaches a delivered artifact.
    """
    for flow in flows:
        source = str(flow.analysis_payload["program"]["source_path"])
        if not source.startswith("/"):
            continue
        assert any("source_path" in item for item in flow.mismatches), (
            "an absolute path was carried and the flow failed to report it"
        )


def test_no_absolute_path_reaches_a_delivered_artifact(flows: list[FlowResult]) -> None:
    """Where an absolute path would actually do damage."""
    for flow in flows:
        assert flow.store is not None
        assert "/Users/" not in flow.rendered_report
        for evidence in flow.store.evidence_for_binary(flow.binary_id):
            assert "/Users/" not in evidence.summary


def test_the_flow_reports_the_report_status_gap(flows: list[FlowResult]) -> None:
    """The engineering report cannot distinguish REJECTED from UNTESTED.

    EVIDENCE-001 pinned the same gap and could not close it: `report.py` is
    outside its ownership and outside this node's. Detected here rather than
    asserted, so the finding disappears on its own once the file is fixed.
    """
    for flow in flows:
        assert flow.store is not None
        current = flow.store.current_hypothesis(flow.binary_id, flow.hypothesis_key)
        assert current is not None
        assert current.status is HypothesisStatus.SUPPORTED
        assert current.status.value not in flow.rendered_report
        assert any("HypothesisStatus" in item for item in flow.mismatches)


def test_interface_observations_do_not_count_as_blockers(flows: list[FlowResult]) -> None:
    """The flow completed with both findings present; neither stops the MVP."""
    for flow in flows:
        assert flow.mismatches, "the flow found nothing, which would be suspicious"
        assert flow.blockers == []
        assert flow.ok is True


# --- the delivered artifact ---


def test_the_committed_report_matches_what_the_flow_produces(
    flows: list[FlowResult],
) -> None:
    """An artifact nobody can re-derive is a claim, not evidence."""
    assert REPORT_PATH.is_file(), f"the integration report is missing at {REPORT_PATH}"
    committed = REPORT_PATH.read_text(encoding="utf-8")

    assert deterministic_part(render_report(flows)) == deterministic_part(committed)


def test_the_report_reproduces_across_runs(tmp_path: Path) -> None:
    """Only the performance section may move between runs."""
    sample = FIXTURES[0]
    first = render_report([run_static_flow(sample, tmp_path / "a.sqlite3")])
    second = render_report([run_static_flow(sample, tmp_path / "b.sqlite3")])

    assert deterministic_part(first) == deterministic_part(second)


def test_the_report_carries_no_environment_noise() -> None:
    """Runs on any host, with or without Ghidra."""
    text = REPORT_PATH.read_text(encoding="utf-8")

    assert "/Users/" not in text
    assert "/home/" not in text
    assert "/private/" not in text
    assert not re.search(r"\b\d{4}-\d{2}-\d{2}T\d{2}:", text), "a timestamp would defeat the diff"


def test_the_report_states_every_category_the_contract_requires() -> None:
    text = REPORT_PATH.read_text(encoding="utf-8")

    for heading in (
        "## Steps",
        "## Warnings",
        "## Interface mismatches",
        "## Open blockers",
        "## Performance",
    ):
        assert heading in text, heading
