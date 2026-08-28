"""What detector verification applies to, and what it may claim when it applies
to nothing.

`verify_detection` holds a fixture to finding exactly what it declared it
planted — no more, so a missed defect is caught, and no less, so an invented one
is too. A fixture that declares nothing is a fixture bug and is reported as one.

A captured transcript declares nothing either, for the opposite reason: nothing
was planted in a real call. Before this, all eight baseline transcripts would
have tripped the fixture-bug branch, and the artifact certifying the first real
baseline would have read `detector_verification=FAIL` under the heading
"Detector disagreed with what the fixtures planted", over a list of genuine
samples.

Letting that read PASS instead would have been worse, not better. A corpus with
nothing planted has not been detector-verified at all, and a status over zero
checks is not a status. Hence three states, and hence the half of this file that
tests the boundary rather than the happy path: scope is derived from verified
capture linkage, so a transcript cannot exempt itself by calling itself a
capture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ecu_recovery.evaluation.agent import evaluate
from ecu_recovery.evaluation.agent.__main__ import main
from ecu_recovery.evaluation.agent.captures import ANSWERED, CaptureRecord, write_capture
from ecu_recovery.evaluation.agent.models import DetectionStatus
from ecu_recovery.evaluation.agent.report import render_report

AUTHORED_CORPUS = Path(__file__).resolve().parent / "transcripts"
ARTIFACTS = Path(__file__).resolve().parents[3] / "artifacts" / "evals" / "agent"
BASE_FIXTURE = AUTHORED_CORPUS / "01-supported.json"

#: What `01-supported` plants: everything clean, every citation resolving.
CLEAN_EXPECTS = {
    "parsed": True,
    "claims": 2,
    "factual_claims": 2,
    "raw_factual_claims": 2,
    "citations": 3,
    "valid_citations": 3,
    "fabricated_citations": 0,
    "unsupported_factual_claims": 0,
    "demotions": 0,
}


def model_call(**overrides: Any) -> dict[str, Any]:
    call: dict[str, Any] = {
        "provider": "openai",
        "requested_model": "an-alias",
        "returned_model": "gpt-snapshot-2026-05-05",
        "model_identity_confirmed": True,
        "response_id": "resp_scope_1",
        "status": "completed",
        "incomplete_reason": "",
        "truncated": False,
        "max_output_tokens": 4096,
        "usage": {"input_tokens": 90, "output_tokens": 12},
        "reasoning_tokens": None,
        "request_digest": "a" * 64,
        "reply_digest": "b" * 64,
        "failure": "",
    }
    call.update(overrides)
    return call


def payload(
    transcript_id: str,
    provenance: str = "authored",
    expects: dict[str, Any] | None = None,
    call: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(BASE_FIXTURE.read_text(encoding="utf-8"))
    body["id"] = transcript_id
    body["provenance"] = provenance
    body["capture_id"] = ""
    body.pop("expects", None)
    if expects is not None:
        body["expects"] = dict(expects)
    body["investigation"]["model_call"] = model_call() if call is None else call
    return body


def freeze(root: Path, body: dict[str, Any]) -> Path:
    (root / "transcripts").mkdir(parents=True, exist_ok=True)
    path = root / "transcripts" / f"{body['id']}.json"
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def capture(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Link a transcript to a capture record that verifies, and freeze it."""
    body["provenance"] = "model"
    record = CaptureRecord(
        transcript_id=str(body["id"]),
        sample_id=str(body["sample_id"]),
        subject=str(body["subject"]),
        outcome=ANSWERED,
        model_call=body["investigation"]["model_call"],
        run_id="scope-test",
        captured_at="2026-08-28T00:00:00Z",
    )
    write_capture(root / "captures", record)
    body["capture_id"] = record.capture_id
    freeze(root, body)
    return body


def run(root: Path) -> Any:
    return evaluate(root / "transcripts")


# --- the defect: a real sample is not a defective fixture ---


def test_a_verified_capture_is_out_of_scope(tmp_path: Path) -> None:
    """No mismatch, and no status claimed over a corpus with nothing planted."""
    capture(tmp_path, payload("baseline-01"))

    result = run(tmp_path)

    assert result.detection_mismatches == ()
    assert result.detection_status is DetectionStatus.NOT_APPLICABLE
    assert result.detection_in_scope == 0


def test_a_corpus_of_captures_never_reports_a_pass(tmp_path: Path) -> None:
    """The repair that would have been worse than the defect.

    Silencing the false FAIL by letting the line read PASS would replace a
    visible wrong answer with an invisible one.
    """
    capture(tmp_path, payload("baseline-01"))
    capture(tmp_path, payload("baseline-02", call=model_call(response_id="resp_scope_2")))

    result = run(tmp_path)

    assert result.detection_status is not DetectionStatus.PASS
    assert result.detection_verified is not True


# --- scope is derived, never self-declared ---


def test_a_forged_model_label_stays_in_detector_scope(tmp_path: Path) -> None:
    """The adversarial case, and the reason scope is not read off the label.

    A transcript that could exempt itself from detector verification by calling
    itself a capture would hand back, in a new place, what the linkage check
    exists to prevent.
    """
    freeze(tmp_path, payload("forged-01", provenance="model"))

    result = run(tmp_path)

    assert result.detection_in_scope == 1
    assert result.detection_status is DetectionStatus.FAIL
    assert "forged-01: fixture declares no detector expectations" in result.detection_mismatches
    assert result.provenance.kind == "authored"


def test_a_missing_capture_leaves_a_transcript_in_scope(tmp_path: Path) -> None:
    body = payload("baseline-01", provenance="model")
    body["capture_id"] = "C-" + "0" * 64
    freeze(tmp_path, body)

    result = run(tmp_path)

    assert result.detection_in_scope == 1
    assert result.detection_status is DetectionStatus.FAIL


def test_an_edited_capture_leaves_its_transcript_in_scope(tmp_path: Path) -> None:
    """Linkage decides scope, so breaking linkage restores scope."""
    body = capture(tmp_path, payload("baseline-01"))
    record_path = tmp_path / "captures" / f"{body['capture_id']}.json"
    stored = json.loads(record_path.read_text(encoding="utf-8"))
    stored["body"]["model_call"]["returned_model"] = "something-nicer"
    record_path.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = run(tmp_path)

    assert result.detection_in_scope == 1
    assert result.detection_status is DetectionStatus.FAIL
    assert result.provenance.kind == "authored"


def test_swapped_captures_leave_both_transcripts_in_scope(tmp_path: Path) -> None:
    first = capture(tmp_path, payload("baseline-01"))
    second = capture(tmp_path, payload("baseline-02", call=model_call(response_id="resp_scope_2")))
    first["capture_id"], second["capture_id"] = second["capture_id"], first["capture_id"]
    freeze(tmp_path, first)
    freeze(tmp_path, second)

    result = run(tmp_path)

    assert result.detection_in_scope == 2
    assert result.detection_status is DetectionStatus.FAIL


# --- authored fixtures are unchanged ---


def test_an_authored_fixture_without_expectations_is_still_a_fixture_bug(tmp_path: Path) -> None:
    """Not what this node repairs. An omission there is still an omission."""
    freeze(tmp_path, payload("authored-01"))

    result = run(tmp_path)

    assert result.detection_in_scope == 1
    assert result.detection_status is DetectionStatus.FAIL
    assert "authored-01: fixture declares no detector expectations" in result.detection_mismatches


def test_a_clean_adversarial_fixture_still_passes(tmp_path: Path) -> None:
    freeze(tmp_path, payload("authored-01", expects=CLEAN_EXPECTS))

    result = run(tmp_path)

    assert result.detection_in_scope == 1
    assert result.detection_status is DetectionStatus.PASS
    assert result.detection_verified is True


def test_a_fixture_whose_declared_vector_is_wrong_still_fails(tmp_path: Path) -> None:
    freeze(tmp_path, payload("authored-01", expects={**CLEAN_EXPECTS, "fabricated_citations": 2}))

    result = run(tmp_path)

    assert result.detection_status is DetectionStatus.FAIL
    assert any("fabricated_citations" in item for item in result.detection_mismatches)


def test_a_fixture_with_an_incomplete_vector_still_fails(tmp_path: Path) -> None:
    """Declaring some fields and not others hides a false positive in the rest."""
    partial = {name: value for name, value in CLEAN_EXPECTS.items() if name != "demotions"}
    freeze(tmp_path, payload("authored-01", expects=partial))

    result = run(tmp_path)

    assert result.detection_status is DetectionStatus.FAIL
    assert any("demotions" in item for item in result.detection_mismatches)


def test_a_mixed_corpus_verifies_its_fixtures_and_exempts_its_captures(tmp_path: Path) -> None:
    capture(tmp_path, payload("baseline-01"))
    freeze(tmp_path, payload("authored-01", expects=CLEAN_EXPECTS))

    result = run(tmp_path)

    assert result.detection_in_scope == 1
    assert result.detection_status is DetectionStatus.PASS
    assert result.detection_mismatches == ()


# --- the status itself ---


def test_scope_is_consulted_before_the_mismatches() -> None:
    """An empty mismatch list means "nothing was wrong" only if something was checked."""
    assert DetectionStatus.of(0, ()) is DetectionStatus.NOT_APPLICABLE
    assert DetectionStatus.of(0, ("something",)) is DetectionStatus.NOT_APPLICABLE
    assert DetectionStatus.of(3, ()) is DetectionStatus.PASS
    assert DetectionStatus.of(3, ("something",)) is DetectionStatus.FAIL


def test_an_unstated_scope_does_not_inherit_a_pass(tmp_path: Path) -> None:
    """The dataclass default. An unstated scope is not evidence of a full check."""
    from ecu_recovery.evaluation.agent.models import AgentEvaluationRun, Provenance

    run_without_scope = AgentEvaluationRun(
        provenance=Provenance(), scores=(), metrics=run_metrics(tmp_path)
    )

    assert run_without_scope.detection_status is DetectionStatus.NOT_APPLICABLE


def run_metrics(tmp_path: Path) -> Any:
    """Real metrics from a one-transcript corpus, so the model is not faked."""
    freeze(tmp_path, payload("authored-01", expects=CLEAN_EXPECTS))
    return evaluate(tmp_path / "transcripts").metrics


def test_not_applicable_is_falsy_in_the_serialized_record(tmp_path: Path) -> None:
    """`null`, not a self-describing string, and the choice is deliberate.

    A consumer that tests this field without thinking should get the safe
    answer. `null` is falsy, so an unverified run reads as unverified; a string
    would be truthy and would read as a pass.
    """
    capture(tmp_path, payload("baseline-01"))

    payload_out = run(tmp_path).as_dict()

    assert payload_out["detection_verified"] is None
    assert not payload_out["detection_verified"]
    assert payload_out["detection_mismatches"] == []


# --- what a reader sees ---


def test_the_report_says_not_applicable_and_why(tmp_path: Path) -> None:
    capture(tmp_path, payload("baseline-01"))

    rendered = render_report(run(tmp_path))

    assert "detector verification: NOT APPLICABLE" in rendered
    assert "nothing for the detector to have found or missed" in rendered
    assert "Detector disagreed with what the fixtures planted" not in rendered
    assert "detector verification: FAIL" not in rendered


def test_the_report_still_says_pass_for_a_verified_fixture_corpus(tmp_path: Path) -> None:
    freeze(tmp_path, payload("authored-01", expects=CLEAN_EXPECTS))

    rendered = render_report(run(tmp_path))

    assert "detector verification: PASS" in rendered


def test_the_command_line_prints_the_tri_state(tmp_path: Path, capsys: Any) -> None:
    capture(tmp_path, payload("baseline-01"))

    main(["--transcripts", str(tmp_path / "transcripts"), "--output", str(tmp_path / "out")])

    printed = capsys.readouterr().out
    assert "detector_verification=NOT_APPLICABLE" in printed
    assert "detector_verification=PASS" not in printed
    assert "detector_verification=FAIL" not in printed


def test_the_command_line_still_prints_pass_over_fixtures(tmp_path: Path, capsys: Any) -> None:
    freeze(tmp_path, payload("authored-01", expects=CLEAN_EXPECTS))

    main(["--transcripts", str(tmp_path / "transcripts"), "--output", str(tmp_path / "out")])

    assert "detector_verification=PASS" in capsys.readouterr().out


# --- nothing else moved ---


def test_the_committed_authored_artifacts_are_unchanged(tmp_path: Path) -> None:
    """The control. Scope is universal over the authored corpus, so its recorded
    results and report must not move by a single byte."""
    main(["--transcripts", str(AUTHORED_CORPUS), "--output", str(tmp_path / "out")])

    for name in ("agent-results.json", "agent-report.md"):
        assert (tmp_path / "out" / name).read_text(encoding="utf-8") == (
            ARTIFACTS / name
        ).read_text(encoding="utf-8"), name
