"""The eight-fixture capture path, proved without spending anything.

`BASELINE-AGENT-001` is the first node here that leaves the machine, and the run
it performs is unrepeatable in the way that matters: a transcript is frozen at
capture and never edited, so a harness defect discovered afterwards costs a
second round of real calls to fix. Everything the harness promises is therefore
checked here first, with doubles.

What is not checked here is whether the agent is any good. That is what the
capture is for, and it has not happened.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from baseline_support import (
    GOOD_REPLY,
    SECRET,
    RecordingProvider,
    fake_session,
    refusal,
    subjects_for,
    write_subject_manifest,
)
from capture_harness import (
    BASELINE_OUTPUT_TOKENS,
    SUBJECT_MANIFEST_SHA256,
    BaselinePreparationError,
    capture_all,
    dataset_samples,
    load_subject_manifest,
)

from ecu_recovery.evaluation.agent import evaluate
from ecu_recovery.evaluation.agent.captures import load_capture, verify_linkage
from ecu_recovery.evaluation.agent.transcripts import parse_transcript


def run(tmp_path: Path, provider: RecordingProvider) -> tuple[Any, ...]:
    return capture_all(
        subjects=subjects_for(dataset_samples()),
        provider=provider,
        session_for=fake_session,
        run_id="baseline-test",
        captured_at="2026-08-28T00:00:00Z",
        transcripts_dir=tmp_path / "transcripts",
        captures_dir=tmp_path / "captures",
    )


def transcripts_of(tmp_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "transcripts").glob("*.json"))
    ]


# --- coverage: eight, and no way to make it fewer ---


def test_the_dataset_declares_exactly_eight_fixtures() -> None:
    assert len(dataset_samples()) == 8
    assert len(set(dataset_samples())) == 8


def test_a_capture_covers_every_fixture(tmp_path: Path) -> None:
    captured = run(tmp_path, RecordingProvider())

    assert len(captured) == 8
    assert {item.sample_id for item in captured} == set(dataset_samples())
    assert len(transcripts_of(tmp_path)) == 8


def test_there_is_no_way_to_capture_a_subset(tmp_path: Path) -> None:
    """A subset parameter is how a baseline becomes a selection.

    Checked on the signature rather than by behaviour, because the failure this
    guards against is a parameter being added later that nothing objects to.
    """
    parameters = set(inspect.signature(capture_all).parameters)

    assert not parameters & {"only", "subset", "samples", "fixtures", "limit", "skip"}


def test_a_partial_subject_set_is_refused(tmp_path: Path) -> None:
    subjects = subjects_for(dataset_samples())
    subjects.pop("lookup_1d_v1")

    with pytest.raises(BaselinePreparationError, match="exactly 8 fixtures"):
        capture_all(
            subjects=subjects,
            provider=RecordingProvider(),
            session_for=fake_session,
            run_id="r",
            captured_at="t",
            transcripts_dir=tmp_path / "transcripts",
            captures_dir=tmp_path / "captures",
        )


def test_an_unknown_sample_is_refused(tmp_path: Path) -> None:
    subjects = subjects_for(dataset_samples())
    subjects["invented_sample_v1"] = "0x1000"

    with pytest.raises(BaselinePreparationError, match="exactly 8 fixtures"):
        capture_all(
            subjects=subjects,
            provider=RecordingProvider(),
            session_for=fake_session,
            run_id="r",
            captured_at="t",
            transcripts_dir=tmp_path / "transcripts",
            captures_dir=tmp_path / "captures",
        )


# --- the budget: 8192, always, and not adjustable ---


def test_every_call_uses_the_baseline_ceiling(tmp_path: Path) -> None:
    provider = RecordingProvider()

    run(tmp_path, provider)

    assert BASELINE_OUTPUT_TOKENS == 8192
    assert {request.max_output_tokens for request in provider.requests} == {8192}


def test_the_ceiling_is_not_a_parameter() -> None:
    """A budget that can be passed in is a budget that can be raised after a
    disappointing answer."""
    parameters = set(inspect.signature(capture_all).parameters)

    assert not parameters & {"budget", "max_output_tokens", "tokens"}


def test_the_ceiling_does_not_move_after_a_truncated_reply(tmp_path: Path) -> None:
    """The adaptive path that must not exist. A truncated answer is a finding."""
    provider = RecordingProvider(truncate={0, 1})

    run(tmp_path, provider)

    assert [request.max_output_tokens for request in provider.requests] == [8192] * 8


def test_the_recorded_ceiling_matches_the_one_used(tmp_path: Path) -> None:
    run(tmp_path, RecordingProvider())

    for transcript in transcripts_of(tmp_path):
        assert transcript["investigation"]["model_call"]["max_output_tokens"] == 8192


# --- one attempt each ---


def test_exactly_one_outbound_attempt_per_fixture(tmp_path: Path) -> None:
    provider = RecordingProvider()

    run(tmp_path, provider)

    assert provider.calls == 8


def test_a_refusal_is_not_retried(tmp_path: Path) -> None:
    """Eight fixtures, three of them refused, still eight calls."""
    provider = RecordingProvider(outcomes={0: refusal(), 3: refusal(), 7: refusal()})

    run(tmp_path, provider)

    assert provider.calls == 8


def test_an_unusable_reply_is_not_retried(tmp_path: Path) -> None:
    provider = RecordingProvider(outcomes={2: "not json at all"})

    run(tmp_path, provider)

    assert provider.calls == 8


def test_no_retry_or_adaptive_parameter_exists() -> None:
    parameters = set(inspect.signature(capture_all).parameters)

    assert not parameters & {"retries", "retry", "attempts", "adapt", "on_failure"}


# --- every outcome is frozen ---


def test_a_refused_call_is_still_captured(tmp_path: Path) -> None:
    provider = RecordingProvider(outcomes={0: refusal()})

    captured = run(tmp_path, provider)

    refused = next(item for item in captured if not item.answered)
    assert "429 rate limit" in str(refused.failure)
    assert refused.transcript_path.is_file()
    assert (tmp_path / "captures" / f"{refused.capture.capture_id}.json").is_file()


def test_a_refused_call_records_what_was_attempted(tmp_path: Path) -> None:
    provider = RecordingProvider(outcomes={0: refusal()})

    run(tmp_path, provider)

    failed = next(t for t in transcripts_of(tmp_path) if t["investigation"]["failure"])
    call = failed["investigation"]["model_call"]
    assert call["max_output_tokens"] == 8192
    assert len(call["request_digest"]) == 64
    assert call["reply_digest"] == ""


def test_an_empty_reply_is_frozen_as_what_happened(tmp_path: Path) -> None:
    provider = RecordingProvider(outcomes={1: "   "})

    captured = run(tmp_path, provider)

    assert len([item for item in captured if not item.answered]) == 1
    assert len(transcripts_of(tmp_path)) == 8


def test_a_truncated_reply_is_frozen_with_its_state(tmp_path: Path) -> None:
    provider = RecordingProvider(truncate={0})

    run(tmp_path, provider)

    truncated = [
        t for t in transcripts_of(tmp_path) if t["investigation"]["model_call"]["truncated"]
    ]
    assert len(truncated) == 1
    assert truncated[0]["investigation"]["model_call"]["incomplete_reason"] == "max_output_tokens"


def test_a_mixed_run_freezes_all_eight(tmp_path: Path) -> None:
    """Good, refused, unusable, truncated, and empty in one run."""
    provider = RecordingProvider(
        outcomes={0: refusal(), 1: "not json", 2: "   "},
        truncate={3},
    )

    captured = run(tmp_path, provider)

    assert len(captured) == 8
    assert len(transcripts_of(tmp_path)) == 8
    assert len(list((tmp_path / "captures").glob("*.json"))) == 8


# --- linkage: every transcript names the record behind it ---


def test_every_transcript_links_to_its_capture(tmp_path: Path) -> None:
    run(tmp_path, RecordingProvider())

    for payload in transcripts_of(tmp_path):
        transcript = parse_transcript(payload)
        assert verify_linkage(transcript, tmp_path / "captures") == ""


def test_a_refused_call_links_too(tmp_path: Path) -> None:
    run(tmp_path, RecordingProvider(outcomes={0: refusal(), 5: refusal()}))

    for payload in transcripts_of(tmp_path):
        assert verify_linkage(parse_transcript(payload), tmp_path / "captures") == ""


def test_the_capture_names_the_transcript_that_carries_it(tmp_path: Path) -> None:
    run(tmp_path, RecordingProvider())

    for payload in transcripts_of(tmp_path):
        record = load_capture(tmp_path / "captures", payload["capture_id"])
        assert record.transcript_id == payload["id"]
        assert record.model_call == payload["investigation"]["model_call"]


def test_the_evaluator_reads_the_run_as_a_real_baseline(tmp_path: Path) -> None:
    """The whole point of the linkage, end to end and with no network."""
    run(tmp_path, RecordingProvider())

    result = evaluate(tmp_path / "transcripts")

    assert result.provenance.kind == "model"
    assert result.baseline_only is False
    assert result.detection_status.value == "NOT_APPLICABLE"


# --- provenance detail survives ---


def test_the_returned_identity_and_response_id_are_frozen(tmp_path: Path) -> None:
    run(tmp_path, RecordingProvider())

    ids = set()
    for payload in transcripts_of(tmp_path):
        call = payload["investigation"]["model_call"]
        assert call["provider"] == "openai"
        assert call["returned_model"] == "gpt-snapshot-2026-05-05"
        assert call["requested_model"] == "an-alias"
        assert call["model_identity_confirmed"] is True
        assert call["usage"]["input_tokens"] > 0
        assert call["reasoning_tokens"] is not None
        ids.add(call["response_id"])
    assert len(ids) == 8


# --- frozen means frozen ---


def test_a_second_capture_over_the_same_directory_is_refused(tmp_path: Path) -> None:
    run(tmp_path, RecordingProvider())

    with pytest.raises(BaselinePreparationError, match="never overwritten"):
        run(tmp_path, RecordingProvider(outcomes={0: "not json"}))


def test_an_identical_rerun_changes_nothing(tmp_path: Path) -> None:
    """Rewriting the same bytes is harmless; it is a different run that is not."""
    run(tmp_path, RecordingProvider())
    before = {p.name: p.read_text(encoding="utf-8") for p in (tmp_path / "transcripts").glob("*")}

    run(tmp_path, RecordingProvider())

    after = {p.name: p.read_text(encoding="utf-8") for p in (tmp_path / "transcripts").glob("*")}
    assert before == after


# --- nothing leaks ---


def test_no_credential_reaches_a_frozen_artifact(tmp_path: Path) -> None:
    """The double returns a key on every call. The allowlist is what stops it."""
    run(tmp_path, RecordingProvider())

    for path in list((tmp_path / "transcripts").glob("*")) + list(
        (tmp_path / "captures").glob("*")
    ):
        text = path.read_text(encoding="utf-8")
        assert SECRET not in text
        assert "org-should-never-appear" not in text
        assert "authorization" not in text.lower()


def test_no_ground_truth_reaches_a_frozen_artifact(tmp_path: Path) -> None:
    """The harness knows an address. What the function does is what is measured."""
    run(tmp_path, RecordingProvider())

    truth = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "samples/synthetic/ground_truth/temperature_controller_v1.json"
        ).read_text(encoding="utf-8")
    )
    roles = list(truth["expected_function_roles"].values())
    for path in (tmp_path / "transcripts").glob("*.json"):
        text = path.read_text(encoding="utf-8")
        for role in roles:
            assert role not in text


def test_the_harness_never_reads_ground_truth() -> None:
    """Checked on the code rather than the text of the file.

    The module's own prose names the files it must not open, in order to say
    that it does not open them, so a substring search over the source would
    fail on the sentence promising the property. Docstrings are dropped and the
    remaining string literals are examined.
    """
    import ast

    source = (Path(__file__).resolve().parent / "capture_harness.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            body = getattr(node, "body", [])
            first = body[0] if body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))

    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]

    assert literals, "no string literals found; the check would pass vacuously"
    for literal in literals:
        assert "ground_truth" not in literal, literal
        assert "firmware.symbols" not in literal, literal
        assert "behavior.dylib" not in literal, literal
    assert "firmware.stripped" in literals


def test_the_transcript_carries_no_ground_truth_role(tmp_path: Path) -> None:
    """Only after a transcript is frozen may ground truth exist for it."""
    run(tmp_path, RecordingProvider())

    for payload in transcripts_of(tmp_path):
        assert "ground_truth_role" not in payload["investigation"]


# --- the manifest gate ---


def test_no_subject_manifest_is_frozen_yet() -> None:
    """The state this branch is in, asserted rather than described.

    Four of the eight samples designate more than one classification function,
    so one subject per fixture is a human choice. Until it is made and its
    digest recorded, the capture cannot start.
    """
    assert SUBJECT_MANIFEST_SHA256 == ""

    with pytest.raises(BaselinePreparationError, match="no subject manifest has been frozen"):
        load_subject_manifest()


def test_a_frozen_manifest_loads_when_its_digest_matches(tmp_path: Path) -> None:
    path = tmp_path / "subject-manifest.json"
    digest = write_subject_manifest(path, subjects_for(dataset_samples()))

    assert load_subject_manifest(path, digest) == subjects_for(dataset_samples())


def test_a_manifest_edited_after_freezing_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "subject-manifest.json"
    digest = write_subject_manifest(path, subjects_for(dataset_samples()))
    write_subject_manifest(path, {**subjects_for(dataset_samples()), "lookup_1d_v1": "0xdead"})

    with pytest.raises(BaselinePreparationError, match="changed after it was frozen"):
        load_subject_manifest(path, digest)


def test_a_manifest_missing_a_fixture_is_refused(tmp_path: Path) -> None:
    subjects = subjects_for(dataset_samples())
    subjects.pop("state_machine_v1")
    path = tmp_path / "subject-manifest.json"
    digest = write_subject_manifest(path, subjects)

    with pytest.raises(BaselinePreparationError, match="missing"):
        load_subject_manifest(path, digest)


def test_a_manifest_with_an_empty_subject_is_refused(tmp_path: Path) -> None:
    subjects = {**subjects_for(dataset_samples()), "state_machine_v1": "  "}
    path = tmp_path / "subject-manifest.json"
    digest = write_subject_manifest(path, subjects)

    with pytest.raises(BaselinePreparationError, match="no subject address"):
        load_subject_manifest(path, digest)


def test_a_missing_manifest_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BaselinePreparationError, match="no subject manifest at"):
        load_subject_manifest(tmp_path / "absent.json", "0" * 64)


def test_the_good_reply_is_what_a_clean_fixture_freezes(tmp_path: Path) -> None:
    """A guard on the double itself, so a broken fake cannot make the rest pass."""
    run(tmp_path, RecordingProvider())

    payload = transcripts_of(tmp_path)[0]
    assert payload["investigation"]["failure"] is None
    assert json.loads(GOOD_REPLY)["claims"][0]["statement"].startswith("the function")
