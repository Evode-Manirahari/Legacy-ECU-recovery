"""Whether a transcript's claim to be a real-model baseline is backed by anything.

Independent review found that it was not. `"provenance": "model"` typed into a
file made the evaluator report `kind == "model"`, `is_real_model` True, and the
sentence *every transcript came from a real provider* — which satisfied two of
`GATE-AGENT-MVP`'s invariants on the strength of a word somebody wrote. These
tests are the adversary that finding described, kept where it can run forever.

What is being checked is **integrity and linkage**, and the wording matters. A
capture record proves it has not been edited since it was written and that it
belongs to the transcript pointing at it. It does not prove a provider made the
call, and nothing a repository can hold would: whoever can write one file can
write two consistent ones. The forgery just has to be deliberate now, and every
certified capture carries the provider-issued response id a human can check
against the provider's own records.

Positive controls are here for the reason negative tests need them: a check that
refuses everything passes every adversarial test and is worthless.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ecu_recovery.evaluation.agent import GATE_TARGETS, evaluate, parse_transcript
from ecu_recovery.evaluation.agent.captures import (
    ANSWERED,
    FAILED,
    CaptureError,
    CaptureRecord,
    load_capture,
    record_for,
    verify_linkage,
    write_capture,
)
from ecu_recovery.evaluation.agent.runner import AUTHORED_DETAIL

AUTHORED_CORPUS = Path(__file__).resolve().parent / "transcripts"

#: A real transcript body, so the scorer has something genuine to score. Only
#: the provenance machinery is under test; borrowing a fixture keeps the rest of
#: the corpus exactly as the scorer already knows it.
BASE_FIXTURE = AUTHORED_CORPUS / "01-supported.json"


def model_call(**overrides: Any) -> dict[str, Any]:
    """The call record a real capture would carry."""
    call: dict[str, Any] = {
        "provider": "openai",
        "requested_model": "an-alias",
        "returned_model": "gpt-snapshot-2026-05-05",
        "model_identity_confirmed": True,
        "response_id": "resp_abc123",
        "status": "completed",
        "incomplete_reason": "",
        "truncated": False,
        "max_output_tokens": 4096,
        "usage": {"input_tokens": 1200, "output_tokens": 350},
        "reasoning_tokens": 280,
        "request_digest": "a" * 64,
        "reply_digest": "b" * 64,
        "failure": "",
    }
    call.update(overrides)
    return call


def transcript_payload(
    transcript_id: str,
    provenance: str = "model",
    capture_id: str = "",
    call: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(BASE_FIXTURE.read_text(encoding="utf-8"))
    payload["id"] = transcript_id
    payload["provenance"] = provenance
    payload["capture_id"] = capture_id
    payload.pop("expects", None)
    payload["investigation"]["model_call"] = model_call() if call is None else call
    return payload


def write_transcript(directory: Path, payload: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{payload['id']}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def captured(
    root: Path,
    transcript_id: str = "baseline-01",
    call: dict[str, Any] | None = None,
    outcome: str = ANSWERED,
) -> tuple[Path, CaptureRecord]:
    """A transcript and the capture record that attests it, correctly linked."""
    payload = transcript_payload(transcript_id, call=call)
    record = CaptureRecord(
        transcript_id=transcript_id,
        sample_id=str(payload["sample_id"]),
        subject=str(payload["subject"]),
        outcome=outcome,
        model_call=payload["investigation"]["model_call"],
        run_id="baseline-run-1",
        captured_at="2026-08-27T00:00:00Z",
    )
    write_capture(root / "captures", record)
    payload["capture_id"] = record.capture_id
    return write_transcript(root / "transcripts", payload), record


def run(root: Path) -> Any:
    return evaluate(root / "transcripts")


def reason_for(root: Path, transcript_path: Path) -> str:
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    return verify_linkage(parse_transcript(payload), root / "captures")


# --- the finding, pinned ---


def test_a_hand_written_model_label_is_not_a_baseline(tmp_path: Path) -> None:
    """The exact forgery independent review demonstrated.

    An authored fixture with one word changed and nothing else. Before the
    linkage check this produced `kind == "model"` and the claim that every
    transcript came from a real provider.
    """
    write_transcript(tmp_path / "transcripts", transcript_payload("forged-01"))

    result = run(tmp_path)

    assert result.provenance.kind == "authored"
    assert result.provenance.is_real_model is False
    assert result.baseline_only is True
    assert "forged-01" in result.provenance.detail
    assert "names no capture record" in result.provenance.detail


def test_the_run_says_which_transcript_failed_and_why(tmp_path: Path) -> None:
    """A run that quietly declines to count a transcript is as opaque as one
    that quietly counts it."""
    write_transcript(tmp_path / "transcripts", transcript_payload("forged-01"))

    detail = run(tmp_path).provenance.detail

    assert "not backed by a verified capture record" in detail


def test_a_missing_capture_record_is_not_a_baseline(tmp_path: Path) -> None:
    payload = transcript_payload("baseline-01", capture_id="C-" + "0" * 64)
    write_transcript(tmp_path / "transcripts", payload)

    result = run(tmp_path)

    assert result.provenance.kind == "authored"
    assert "no capture record" in result.provenance.detail


def test_an_edited_capture_record_is_not_a_baseline(tmp_path: Path) -> None:
    """One field changed, the identifier left alone. The record no longer
    matches its own contents."""
    transcript, record = captured(tmp_path)
    path = tmp_path / "captures" / f"{record.capture_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["body"]["model_call"]["returned_model"] = "a-better-sounding-model"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert "edited after it was written" in reason_for(tmp_path, transcript)
    assert run(tmp_path).provenance.kind == "authored"


def test_a_record_edited_consistently_still_fails_its_transcript(tmp_path: Path) -> None:
    """Body and header changed together, so the record is internally consistent.

    It is still not the record this transcript names, because the filename and
    the transcript's reference both carry the identifier of what was captured.
    """
    transcript, record = captured(tmp_path)
    path = tmp_path / "captures" / f"{record.capture_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["body"]["model_call"]["returned_model"] = "a-better-sounding-model"
    rebuilt = CaptureRecord.from_dict(payload)
    payload["capture_id"] = rebuilt.capture_id
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    reason = reason_for(tmp_path, transcript)

    assert "does not match its own contents" in reason
    assert run(tmp_path).provenance.kind == "authored"


def test_swapped_capture_identifiers_are_not_a_baseline(tmp_path: Path) -> None:
    """Two real captures, each transcript pointing at the other's record."""
    first, first_record = captured(tmp_path, "baseline-01")
    second, second_record = captured(
        tmp_path, "baseline-02", call=model_call(response_id="resp_def456")
    )

    for path, other in ((first, second_record), (second, first_record)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["capture_id"] = other.capture_id
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = run(tmp_path)

    assert result.provenance.kind == "authored"
    assert "not for this transcript" in result.provenance.detail


def test_a_transcript_edited_after_its_capture_is_not_a_baseline(tmp_path: Path) -> None:
    """The record is untouched; the transcript's own call block was changed."""
    transcript, _ = captured(tmp_path)
    payload = json.loads(transcript.read_text(encoding="utf-8"))
    payload["investigation"]["model_call"]["returned_model"] = "something-else"
    transcript.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert "disagree" in reason_for(tmp_path, transcript)
    assert run(tmp_path).provenance.kind == "authored"


def test_a_transcript_with_no_call_record_has_nothing_to_attest(tmp_path: Path) -> None:
    transcript, _ = captured(tmp_path)
    payload = json.loads(transcript.read_text(encoding="utf-8"))
    payload["investigation"].pop("model_call")
    transcript.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert "records no model call" in reason_for(tmp_path, transcript)


def test_a_scripted_provider_cannot_certify_a_real_model_run(tmp_path: Path) -> None:
    """A capture honest about being scripted is still not a baseline."""
    transcript, _ = captured(tmp_path, call=model_call(provider="scripted"))

    assert "not a real provider" in reason_for(tmp_path, transcript)
    assert run(tmp_path).provenance.kind == "authored"


def test_an_answered_capture_without_a_response_id_is_not_a_baseline(tmp_path: Path) -> None:
    """The response id is the only field checkable outside this repository.

    Without it the capture is internally consistent and externally unverifiable,
    which is precisely the state this node exists to stop being called proof.
    """
    transcript, _ = captured(tmp_path, call=model_call(response_id=""))

    assert "no provider-issued response id" in reason_for(tmp_path, transcript)


def test_a_capture_identifier_cannot_escape_its_directory(tmp_path: Path) -> None:
    """The identifier arrives from a file and reaches the filesystem."""
    payload = transcript_payload("baseline-01", capture_id="../../../../etc/passwd")
    write_transcript(tmp_path / "transcripts", payload)

    result = run(tmp_path)

    assert result.provenance.kind == "authored"
    assert "is not a capture identifier" in result.provenance.detail


def test_a_mixed_corpus_is_not_a_baseline(tmp_path: Path) -> None:
    """One verified real transcript beside one honest authored fixture."""
    captured(tmp_path, "baseline-01")
    write_transcript(
        tmp_path / "transcripts", transcript_payload("authored-01", provenance="authored")
    )

    result = run(tmp_path)

    assert result.provenance.kind == "authored"
    assert result.baseline_only is True
    assert "mixed corpus" in result.provenance.detail


def test_one_unverifiable_transcript_makes_the_whole_run_authored(tmp_path: Path) -> None:
    """A valid capture next to a forged claim. All or nothing, as before."""
    captured(tmp_path, "baseline-01")
    write_transcript(tmp_path / "transcripts", transcript_payload("forged-02"))

    result = run(tmp_path)

    assert result.provenance.kind == "authored"
    assert "forged-02" in result.provenance.detail
    assert "baseline-01" not in result.provenance.detail


# --- positive controls: the check must be capable of saying yes ---


def test_a_verified_capture_is_a_model_run(tmp_path: Path) -> None:
    captured(tmp_path, "baseline-01")

    result = run(tmp_path)

    assert result.provenance.kind == "model"
    assert result.provenance.is_real_model is True
    assert result.baseline_only is False


def test_the_run_detail_does_not_overclaim_what_was_verified(tmp_path: Path) -> None:
    """A hash proves the artifact, not that a provider answered.

    The sentence a reader sees above the numbers has to say which of the two it
    means, because a gate result that overstates its own evidence is the failure
    this whole node is about.
    """
    captured(tmp_path, "baseline-01")

    detail = run(tmp_path).provenance.detail

    assert "verified capture record" in detail
    assert "not proof that a provider made the call" in detail
    assert "response ids" in detail


def test_a_failed_call_is_still_a_verifiable_capture(tmp_path: Path) -> None:
    """A timeout is a real sample. A baseline that drops them is curated.

    No response id exists for a call that never returned, so an answered
    capture's requirement cannot apply to this one.
    """
    transcript, _ = captured(
        tmp_path,
        call=model_call(response_id="", reply_digest="", failure="model unavailable: timed out"),
        outcome=FAILED,
    )

    assert reason_for(tmp_path, transcript) == ""
    assert run(tmp_path).provenance.kind == "model"


# --- the record itself ---


def test_capture_identity_is_derived_from_the_whole_body(tmp_path: Path) -> None:
    """Every field is inside the digest, so no field can be changed unnoticed."""
    _, record = captured(tmp_path)
    baseline = record.capture_id

    from dataclasses import replace

    assert replace(record, subject="0xdeadbeef").capture_id != baseline
    assert replace(record, sample_id="other_sample").capture_id != baseline
    assert replace(record, transcript_id="other-transcript").capture_id != baseline
    assert replace(record, run_id="another-run").capture_id != baseline
    assert replace(record, captured_at="2020-01-01T00:00:00Z").capture_id != baseline
    assert replace(record, model_call=model_call(response_id="resp_z")).capture_id != baseline


def test_the_same_record_always_has_the_same_identity(tmp_path: Path) -> None:
    _, first = captured(tmp_path, "baseline-01")
    second = CaptureRecord.from_dict(
        json.loads((tmp_path / "captures" / f"{first.capture_id}.json").read_text(encoding="utf-8"))
    )

    assert second.capture_id == first.capture_id


def test_a_record_must_name_the_transcript_it_belongs_to() -> None:
    with pytest.raises(CaptureError, match="must name the transcript"):
        CaptureRecord(transcript_id=" ", sample_id="s", subject="0x1", outcome=ANSWERED)


def test_an_outcome_outside_the_two_real_ones_is_refused() -> None:
    with pytest.raises(CaptureError, match="outcome must be"):
        CaptureRecord(transcript_id="t", sample_id="s", subject="0x1", outcome="probably-fine")


def test_writing_never_replaces_a_different_record(tmp_path: Path) -> None:
    """Records are immutable. Rewriting the identical one is a no-op."""
    _, record = captured(tmp_path)
    write_capture(tmp_path / "captures", record)

    path = tmp_path / "captures" / f"{record.capture_id}.json"
    path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(CaptureError, match="already stands"):
        write_capture(tmp_path / "captures", record)


def test_a_record_built_from_an_investigation_follows_the_reply(tmp_path: Path) -> None:
    """The outcome describes what arrived, not the verdict on it."""
    answered_record = record_for("t", "s", "0x1", {"model_call": model_call()})
    failed_record = record_for("t", "s", "0x1", {"model_call": model_call(reply_digest="")})

    assert answered_record.outcome == ANSWERED
    assert failed_record.outcome == FAILED


def test_an_investigation_without_a_call_cannot_be_captured() -> None:
    with pytest.raises(CaptureError, match="records no model call"):
        record_for("t", "s", "0x1", {})


def test_loading_refuses_an_identifier_that_is_not_one(tmp_path: Path) -> None:
    with pytest.raises(CaptureError, match="not a capture identifier"):
        load_capture(tmp_path, "C-nope")


# --- nothing else moved ---


def test_the_authored_corpus_is_unaffected() -> None:
    """The control for this repair. Its recorded score must not change."""
    result = evaluate(AUTHORED_CORPUS)

    assert result.provenance.kind == "authored"
    assert result.provenance.detail == AUTHORED_DETAIL
    assert result.baseline_only is True


def test_the_hard_thresholds_are_untouched() -> None:
    """The repair changes what counts as a real baseline, not what passing is."""
    assert GATE_TARGETS == (
        ("evidence_reference_validity", "==", 100.0),
        ("schema_compliance", "==", 100.0),
        ("unsupported_factual_claims", "<=", 5.0),
        ("tool_hallucinations", "==", 0.0),
        ("critical_unsupported_claims", "==", 0.0),
    )
