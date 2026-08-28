"""What has to be true before the first outbound call, and what it costs if not.

Three defects found in an independent pre-spend review are pinned here. They
shared a shape worth naming, because it is the shape that survives a green
suite: each one was a check that existed and ran, but ran *after* the money.
The frozen manifest was loadable and never compared against; the freeze on a
completed baseline was enforced one fixture at a time, after that fixture's
call; the credential was validated inside the call rather than before it.

So every test here asserts the same three things together — the run is refused,
the provider was called zero times, and nothing was written. A refusal that
arrives after one call is not a refusal, it is a receipt.

Nothing here reaches a network. `RecordingProvider` counts calls it never makes
outbound, and the live transport is only ever constructed unconfigured, which
is refused before it could resolve a client.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from baseline_support import RecordingProvider, fake_session, subjects_for, write_subject_manifest
from capture_harness import (
    BaselinePreparationError,
    capture_all,
    check_subjects_are_frozen,
    dataset_samples,
    load_subject_manifest,
    preflight_destinations,
    require_provider_configuration,
    run_live_baseline,
)
from test_transport_preflight import available

from ecu_recovery.evaluation.agent import evaluate
from ecu_recovery.evaluation.agent.transcripts import TranscriptError
from ecu_recovery.providers.openai import OpenAIProvider

#: Shaped like a credential, and never expected to leave this module.
FAKE_KEY = "sk-proj-PreSpendGuardsMustNeverEchoThis"
CONFIGURED = {"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": "a-snapshot-2026-05-05"}


def frozen(tmp_path: Path) -> tuple[dict[str, str], Path, str]:
    subjects = subjects_for(dataset_samples())
    path = tmp_path / "subject-manifest.json"
    return subjects, path, write_subject_manifest(path, subjects)


def artifacts(tmp_path: Path) -> dict[str, str]:
    """Every frozen byte under a run, so a test can prove nothing moved."""
    return {
        f"{name}/{path.name}": path.read_text(encoding="utf-8")
        for name in ("transcripts", "captures")
        for path in sorted((tmp_path / name).glob("*.json"))
    }


def capture(tmp_path: Path, provider: Any, subjects: dict[str, str], **kw: Any) -> tuple[Any, ...]:
    _, manifest_path, identity = frozen(tmp_path)
    return capture_all(
        subjects=subjects,
        provider=provider,
        session_for=fake_session,
        run_id="guard-test",
        captured_at="2026-08-28T00:00:00Z",
        transcripts_dir=tmp_path / "transcripts",
        captures_dir=tmp_path / "captures",
        manifest_path=manifest_path,
        expected_manifest_id=identity,
        **kw,
    )


def assert_nothing_happened(tmp_path: Path, provider: RecordingProvider) -> None:
    """The three facts that together mean a refusal was free."""
    assert provider.calls == 0
    assert artifacts(tmp_path) == {}


# --- finding 1: the frozen manifest is the authority, not a suggestion ---


def test_a_mutated_subject_address_is_refused_before_any_call(tmp_path: Path) -> None:
    """Reproduced: one address changed, and the capture went ahead regardless.

    Coverage was checked and passed — eight fixtures, exactly the dataset's —
    which is precisely why this got through. Where in each binary the model is
    pointed is the easier thing to change and the harder thing to notice.
    """
    subjects = {**subjects_for(dataset_samples()), "bitmask_manipulation_v1": "0xdeadbeef"}
    provider = RecordingProvider()

    with pytest.raises(BaselinePreparationError, match="not the frozen ones"):
        capture(tmp_path, provider, subjects)

    assert_nothing_happened(tmp_path, provider)


def test_every_single_address_is_load_bearing(tmp_path: Path) -> None:
    """Not just the first one. Each of the eight, changed alone, stops the run."""
    for sample_id in dataset_samples():
        subjects = {**subjects_for(dataset_samples()), sample_id: "0xdeadbeef"}
        provider = RecordingProvider()
        destination = tmp_path / sample_id
        destination.mkdir()

        with pytest.raises(BaselinePreparationError, match=sample_id):
            capture(destination, provider, subjects)

        assert provider.calls == 0


def test_the_refusal_names_which_subject_moved(tmp_path: Path) -> None:
    subjects = {**subjects_for(dataset_samples()), "state_machine_v1": "0x1"}
    with pytest.raises(BaselinePreparationError) as raised:
        capture(tmp_path, RecordingProvider(), subjects)

    assert "state_machine_v1" in str(raised.value)
    assert "lookup_1d_v1" not in str(raised.value)


def test_a_manifest_edited_after_freezing_stops_the_capture(tmp_path: Path) -> None:
    """The manifest itself changing is refused on the same side of the money."""
    subjects, manifest_path, identity = frozen(tmp_path)
    write_subject_manifest(manifest_path, {**subjects, "lookup_2d_v1": "0xbad"})
    provider = RecordingProvider()

    with pytest.raises(BaselinePreparationError, match="it changed after it was frozen"):
        capture_all(
            subjects=subjects,
            provider=provider,
            session_for=fake_session,
            run_id="r",
            captured_at="t",
            transcripts_dir=tmp_path / "transcripts",
            captures_dir=tmp_path / "captures",
            manifest_path=manifest_path,
            expected_manifest_id=identity,
        )

    assert_nothing_happened(tmp_path, provider)


def test_the_frozen_subjects_are_the_ones_captured(tmp_path: Path) -> None:
    """The positive control. A check that refuses everything proves nothing."""
    subjects, _, _ = frozen(tmp_path)
    captured = capture(tmp_path, RecordingProvider(), subjects)

    assert len(captured) == 8
    for item in captured:
        assert item.subject == subjects[item.sample_id]
    for path in (tmp_path / "transcripts").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["subject"] == subjects[payload["sample_id"]]


def test_the_live_path_reads_the_frozen_manifest_and_nothing_else() -> None:
    """Structural: the entry point that spends is wired to `load_subject_manifest`.

    Asserted on the source because the failure guarded against is a future
    edit that resolves subjects some other way — from a literal, an argument,
    or a scan — which no behavioural test would object to.
    """
    source = inspect.getsource(run_live_baseline)

    assert "load_subject_manifest()" in source
    assert "subjects" not in inspect.signature(run_live_baseline).parameters


# --- finding 2: one shot, decided before the first call ---


def test_a_second_run_after_a_completed_baseline_costs_nothing(tmp_path: Path) -> None:
    """Reproduced: the rerun made call #1, wrote capture #1, then objected.

    The transcript freeze caught it, but only for the fixture whose call had
    already happened — so a rerun cost one live call and left one orphan
    capture record behind pointing at a transcript that was never written.
    """
    subjects, _, _ = frozen(tmp_path)
    capture(tmp_path, RecordingProvider(), subjects)
    before = artifacts(tmp_path)

    second = RecordingProvider(outcomes={0: json.dumps({"claims": []})})
    with pytest.raises(BaselinePreparationError, match="already stands here"):
        capture(tmp_path, second, subjects)

    assert second.calls == 0
    assert artifacts(tmp_path) == before


def test_a_lone_stray_capture_aborts_the_whole_run(tmp_path: Path) -> None:
    """Partial state counts. An interrupted run is not resumed automatically."""
    subjects, _, _ = frozen(tmp_path)
    (tmp_path / "captures").mkdir()
    (tmp_path / "captures" / "C-stray.json").write_text("{}", encoding="utf-8")
    provider = RecordingProvider()

    with pytest.raises(BaselinePreparationError, match="already stands here"):
        capture(tmp_path, provider, subjects)

    assert provider.calls == 0
    assert not (tmp_path / "transcripts").exists()


def test_a_lone_stray_transcript_aborts_the_whole_run(tmp_path: Path) -> None:
    subjects, _, _ = frozen(tmp_path)
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "transcripts" / "baseline-lookup_1d_v1.json").write_text("{}", encoding="utf-8")
    provider = RecordingProvider()

    with pytest.raises(BaselinePreparationError, match="already stands here"):
        capture(tmp_path, provider, subjects)

    assert provider.calls == 0
    assert not (tmp_path / "captures").exists()


def test_an_empty_destination_proceeds(tmp_path: Path) -> None:
    """Positive control: the preflight refuses prior state, not every run."""
    subjects, _, _ = frozen(tmp_path)
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "captures").mkdir()

    assert len(capture(tmp_path, RecordingProvider(), subjects)) == 8


def test_the_preflight_is_reached_before_the_provider(tmp_path: Path) -> None:
    """Ordering, proved by a provider that would explode if it were consulted."""
    subjects, _, _ = frozen(tmp_path)
    (tmp_path / "captures").mkdir()
    (tmp_path / "captures" / "C-stray.json").write_text("{}", encoding="utf-8")
    exploding = RecordingProvider(outcomes={0: AssertionError("the provider was reached")})

    with pytest.raises(BaselinePreparationError, match="already stands here"):
        capture(tmp_path, exploding, subjects)

    assert exploding.calls == 0


def test_preflight_says_what_is_in_the_way(tmp_path: Path) -> None:
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "captures").mkdir()
    (tmp_path / "captures" / "C-abc.json").write_text("{}", encoding="utf-8")

    with pytest.raises(BaselinePreparationError, match="C-abc.json"):
        preflight_destinations(tmp_path / "transcripts", tmp_path / "captures")


# --- finding 3: configuration is checked before evidence is created ---


@pytest.mark.parametrize(
    ("environ", "named"),
    [
        ({}, "OPENAI_API_KEY, OPENAI_MODEL"),
        ({"OPENAI_MODEL": "a-model"}, "OPENAI_API_KEY"),
        ({"OPENAI_API_KEY": FAKE_KEY}, "OPENAI_MODEL"),
        ({"OPENAI_API_KEY": "   ", "OPENAI_MODEL": "a-model"}, "OPENAI_API_KEY"),
        ({"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": "\t"}, "OPENAI_MODEL"),
    ],
)
def test_missing_configuration_creates_no_baseline_evidence(
    tmp_path: Path, environ: dict[str, str], named: str
) -> None:
    """Reproduced: an unset key produced eight transcripts of failures.

    It did not crash the run, which is what made it dangerous. `investigate`
    records an unreachable provider as an *outcome*, so every fixture froze a
    transcript labelled `provenance: model` backed by a capture record the
    evaluator verified — a complete baseline of nothing that reads exactly like
    a real one taken during an outage.
    """
    with pytest.raises(BaselinePreparationError, match="not configured") as raised:
        run_live_baseline(
            "r",
            "2026-08-28T00:00:00Z",
            tmp_path / "transcripts",
            tmp_path / "captures",
            session_for=fake_session,
            environ=environ,
        )

    assert named in str(raised.value)
    assert not (tmp_path / "transcripts").exists()
    assert not (tmp_path / "captures").exists()


def test_a_refused_run_leaves_nothing_the_evaluator_can_call_a_model_baseline(
    tmp_path: Path,
) -> None:
    """The consequence the guard exists for, asserted through the evaluator."""
    transcripts = tmp_path / "transcripts"
    with pytest.raises(BaselinePreparationError):
        run_live_baseline(
            "r", "t", transcripts, tmp_path / "captures", session_for=fake_session, environ={}
        )

    transcripts.mkdir(parents=True, exist_ok=True)
    with pytest.raises(TranscriptError, match="no transcripts found"):
        evaluate(transcripts)


def test_the_configuration_refusal_never_echoes_the_key(tmp_path: Path) -> None:
    """The message names variables, never values."""
    with pytest.raises(BaselinePreparationError) as raised:
        run_live_baseline(
            "r",
            "t",
            tmp_path / "transcripts",
            tmp_path / "captures",
            session_for=fake_session,
            environ={"OPENAI_API_KEY": FAKE_KEY},
        )

    assert FAKE_KEY not in str(raised.value)
    assert "OPENAI_MODEL" in str(raised.value)


def test_a_live_provider_handed_straight_to_capture_all_is_refused(tmp_path: Path) -> None:
    """The guard belongs to the capture, not to the entry point somebody used."""
    subjects, _, _ = frozen(tmp_path)

    with pytest.raises(BaselinePreparationError, match="not configured"):
        capture(tmp_path, OpenAIProvider(model="a-model"), subjects, environ={})

    assert not (tmp_path / "transcripts").exists()
    assert not (tmp_path / "captures").exists()


def test_a_configured_run_passes_the_check_and_meets_the_next_guard(tmp_path: Path) -> None:
    """Positive control, stopped short of spending anything.

    Configuration is valid and the transport is present, so the refusal that
    arrives is the destination preflight's — which is the proof that the
    earlier checks let the run through rather than that they never ran.

    The transport is supplied as a double. `BASELINE-PREFLIGHT-001` added a
    readiness check between configuration and the destination, and this suite
    runs on a host with no SDK installed; without the double the refusal here
    would be the transport's, and the test would no longer be about
    configuration at all.
    """
    (tmp_path / "captures").mkdir()
    (tmp_path / "captures" / "C-stray.json").write_text("{}", encoding="utf-8")

    with pytest.raises(BaselinePreparationError, match="already stands here"):
        run_live_baseline(
            "r",
            "t",
            tmp_path / "transcripts",
            tmp_path / "captures",
            session_for=fake_session,
            environ=CONFIGURED,
            import_module=available(),
        )


def test_the_checked_identifier_is_returned_and_stripped() -> None:
    assert require_provider_configuration(CONFIGURED) == "a-snapshot-2026-05-05"
    assert require_provider_configuration({**CONFIGURED, "OPENAI_MODEL": "  m  "}) == "m"


def test_the_guards_run_before_the_capture_loop() -> None:
    """Structural: every refusal is above the line that iterates fixtures."""
    source = inspect.getsource(capture_all)
    body, _, loop = source.partition("return tuple(")

    for guard in (
        "check_subjects_are_frozen",
        "require_provider_configuration",
        "require_transport",
        "preflight",
    ):
        assert guard in body, f"{guard} must run before the first call"
        assert guard not in loop


def test_no_credential_reaches_the_frozen_subjects_check(tmp_path: Path) -> None:
    """`check_subjects_are_frozen` reads a manifest and nothing else."""
    subjects, manifest_path, identity = frozen(tmp_path)

    check_subjects_are_frozen(subjects, manifest_path, identity)

    assert FAKE_KEY not in manifest_path.read_text(encoding="utf-8")
    assert load_subject_manifest(manifest_path, identity) == subjects
