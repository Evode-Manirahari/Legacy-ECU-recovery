"""Whether the transport exists here, asked before anything is spent.

The defect this pins is the fourth of a family, and the family is the point:
each member was a check that existed and ran, but ran *after* the money. The
first three were closed in #50. This one walked past all of them, because
configuration being *present* is not the transport being *available*.

With both variables set correctly and the `openai` extra absent, the
configuration guard passes, the SDK import fails inside the call, `investigate`
records an unreachable provider as an **outcome** rather than an error, and the
run completes: eight transcripts labelled `provenance: model`, eight capture
records the evaluator verifies, `is_real_model=True`, and not one request off
the machine. A complete baseline of nothing, indistinguishable from a real one
taken during an outage.

Nothing here touches a network, and neither does the check under test. The
transport is simulated in both directions with a double, which is also what lets
the whole file run on a host with no SDK installed - the condition this node
exists to make safe, and therefore the condition its own tests run under.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from baseline_support import RecordingProvider, fake_session, subjects_for, write_subject_manifest
from capture_harness import (
    TRANSPORT_INSTALL,
    TRANSPORT_MODULE,
    TRANSPORT_SYMBOL,
    BaselinePreparationError,
    capture_all,
    dataset_samples,
    require_transport,
    run_live_baseline,
)

from ecu_recovery.providers.openai import OpenAIProvider

FAKE_KEY = "sk-proj-TransportPreflightMustNeverEchoThis"
CONFIGURED = {"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": "a-snapshot-2026-05-05"}


class _Transport:
    """Stands in for the SDK. Never contacts anything, which is the point."""

    __version__ = "9.9.9"

    def __init__(self, symbol: bool = True) -> None:
        if symbol:
            setattr(self, TRANSPORT_SYMBOL, object())


def available(symbol: bool = True) -> Any:
    """An importer that finds the transport."""
    return lambda name: _Transport(symbol)


def absent(error: BaseException | None = None) -> Any:
    """An importer that does not, in whatever way a broken install would."""

    def _load(name: str) -> Any:
        raise error or ModuleNotFoundError(f"No module named {name!r}")

    return _load


def frozen(tmp_path: Path) -> tuple[dict[str, str], Path, str]:
    subjects = subjects_for(dataset_samples())
    path = tmp_path / "subject-manifest.json"
    return subjects, path, write_subject_manifest(path, subjects)


def artifacts(tmp_path: Path) -> dict[str, str]:
    return {
        f"{name}/{path.name}": path.read_text(encoding="utf-8")
        for name in ("transcripts", "captures")
        if (tmp_path / name).is_dir()
        for path in sorted((tmp_path / name).glob("*.json"))
    }


def live(tmp_path: Path, **kw: Any) -> tuple[Any, ...]:
    return run_live_baseline(
        "preflight-test",
        "2026-08-28T00:00:00Z",
        tmp_path / "transcripts",
        tmp_path / "captures",
        session_for=fake_session,
        environ=CONFIGURED,
        **kw,
    )


# --- the reproduced defect ---


def test_a_configured_run_with_no_transport_is_refused_before_iteration(tmp_path: Path) -> None:
    """Reproduced: this completed, and produced a baseline of eight failures.

    Every variable set, every earlier guard satisfied, and the run went ahead to
    freeze eight transcripts the evaluator reads as a real-model baseline.
    """
    with pytest.raises(BaselinePreparationError, match="not importable here"):
        live(tmp_path, import_module=absent())

    assert artifacts(tmp_path) == {}


def test_the_refusal_costs_no_call_and_no_artifact(tmp_path: Path) -> None:
    """The three facts that together mean the refusal was free."""
    with pytest.raises(BaselinePreparationError):
        live(tmp_path, import_module=absent())

    assert not (tmp_path / "transcripts").exists()
    assert not (tmp_path / "captures").exists()


def test_an_existing_baseline_elsewhere_is_not_mutated(tmp_path: Path) -> None:
    """A refused run must not disturb a capture that already happened."""
    subjects, manifest_path, identity = frozen(tmp_path)
    done = tmp_path / "done"
    capture_all(
        subjects=subjects,
        provider=RecordingProvider(),
        session_for=fake_session,
        run_id="earlier",
        captured_at="2026-08-27T00:00:00Z",
        transcripts_dir=done / "transcripts",
        captures_dir=done / "captures",
        manifest_path=manifest_path,
        expected_manifest_id=identity,
    )
    before = artifacts(done)
    assert len(before) == 16

    with pytest.raises(BaselinePreparationError):
        live(tmp_path / "fresh", import_module=absent())

    assert artifacts(done) == before


@pytest.mark.parametrize(
    "error",
    [
        ModuleNotFoundError("No module named 'openai'"),
        ImportError("cannot import name 'OpenAI'"),
        RuntimeError("the installed package is broken"),
    ],
)
def test_any_import_failure_counts_as_unready(tmp_path: Path, error: BaseException) -> None:
    """A findable-but-broken install is unreadiness too, not just an absent one."""
    with pytest.raises(BaselinePreparationError, match="not importable here"):
        live(tmp_path, import_module=absent(error))

    assert artifacts(tmp_path) == {}


def test_a_transport_without_the_expected_symbol_is_refused(tmp_path: Path) -> None:
    """Importable is not the same as being the thing the adapter reaches for."""
    with pytest.raises(BaselinePreparationError, match=f"exposes no {TRANSPORT_SYMBOL}"):
        live(tmp_path, import_module=available(symbol=False))

    assert artifacts(tmp_path) == {}


def test_the_refusal_says_what_to_do_next() -> None:
    with pytest.raises(BaselinePreparationError) as raised:
        require_transport(absent())

    assert TRANSPORT_MODULE in str(raised.value)
    assert TRANSPORT_INSTALL in str(raised.value)
    assert "--frozen" in str(raised.value)


def test_the_refusal_never_echoes_the_key(tmp_path: Path) -> None:
    """A key-shaped value is configured, and the message is about a module."""
    with pytest.raises(BaselinePreparationError) as raised:
        live(tmp_path, import_module=absent(ImportError(f"context: {FAKE_KEY}")))

    assert FAKE_KEY not in str(raised.value)


# --- the check stays local ---


def test_the_check_reads_no_credential_and_builds_no_client() -> None:
    """Structural, because "it did not call out" is not observable from a pass.

    The body must not mention the environment, a client, a request, or the
    provider package. What it may do is import a module and look at it.
    """
    source = inspect.getsource(require_transport)

    for forbidden in ("environ", "os.", "api_key", "OpenAIProvider", "complete(", "responses"):
        assert forbidden not in source, f"the readiness check must not mention {forbidden}"


def test_the_check_makes_no_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any socket use fails the test rather than reaching anything."""
    import socket

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the readiness check attempted network I/O")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    assert require_transport(available()) == "9.9.9"


def test_no_probe_request_was_added_to_the_live_path() -> None:
    """The scope boundary from the contract, asserted on the source."""
    source = inspect.getsource(run_live_baseline)

    for forbidden in ("responses.create", "models.list", ".ping(", "health_check", "httpx"):
        assert forbidden not in source


# --- positive controls ---


def test_an_available_transport_lets_the_run_through(tmp_path: Path) -> None:
    """A check that refuses everything passes every adversarial test."""
    subjects, manifest_path, identity = frozen(tmp_path)
    captured = capture_all(
        subjects=subjects,
        provider=RecordingProvider(),
        session_for=fake_session,
        run_id="r",
        captured_at="t",
        transcripts_dir=tmp_path / "transcripts",
        captures_dir=tmp_path / "captures",
        manifest_path=manifest_path,
        expected_manifest_id=identity,
        import_module=available(),
    )

    assert len(captured) == 8
    assert len(artifacts(tmp_path)) == 16


def test_an_available_transport_reaches_the_next_guard(tmp_path: Path) -> None:
    """Transport present, destination occupied: the *destination* refuses.

    Which is the proof that the readiness check let the run through rather than
    that it never ran.
    """
    (tmp_path / "captures").mkdir(parents=True)
    (tmp_path / "captures" / "C-stray.json").write_text("{}", encoding="utf-8")

    with pytest.raises(BaselinePreparationError, match="already stands here"):
        live(tmp_path, import_module=available())


def test_the_version_is_reported_back() -> None:
    assert require_transport(available()) == "9.9.9"


def test_a_double_never_needs_a_transport(tmp_path: Path) -> None:
    """The check is for a live provider only; a scripted one imports nothing."""
    subjects, manifest_path, identity = frozen(tmp_path)

    captured = capture_all(
        subjects=subjects,
        provider=RecordingProvider(),
        session_for=fake_session,
        run_id="r",
        captured_at="t",
        transcripts_dir=tmp_path / "transcripts",
        captures_dir=tmp_path / "captures",
        manifest_path=manifest_path,
        expected_manifest_id=identity,
        import_module=absent(),
    )

    assert len(captured) == 8


def test_a_live_provider_handed_to_capture_all_is_checked_too(tmp_path: Path) -> None:
    """The guarantee belongs to the capture, not to the entry point used."""
    subjects, manifest_path, identity = frozen(tmp_path)

    with pytest.raises(BaselinePreparationError, match="not importable here"):
        capture_all(
            subjects=subjects,
            provider=OpenAIProvider(model="a-model"),
            session_for=fake_session,
            run_id="r",
            captured_at="t",
            transcripts_dir=tmp_path / "transcripts",
            captures_dir=tmp_path / "captures",
            manifest_path=manifest_path,
            expected_manifest_id=identity,
            environ=CONFIGURED,
            import_module=absent(),
        )

    assert artifacts(tmp_path) == {}


# --- the protocol this node must not have moved ---


def test_configuration_is_still_checked_before_the_transport(tmp_path: Path) -> None:
    """Unconfigured is still the first thing said, not a module complaint."""
    with pytest.raises(BaselinePreparationError, match="not configured"):
        run_live_baseline(
            "r",
            "t",
            tmp_path / "transcripts",
            tmp_path / "captures",
            session_for=fake_session,
            environ={},
            import_module=absent(),
        )


def test_the_frozen_manifest_is_untouched() -> None:
    from capture_harness import SUBJECT_MANIFEST_ID, load_subject_manifest

    assert SUBJECT_MANIFEST_ID == (
        "M-dd677b4a5603966052d08feb7de8e7f01d98a6186044ed7cea4fd93ecacd0248"
    )
    assert len(load_subject_manifest()) == 8


def test_the_capture_protocol_is_unchanged(tmp_path: Path) -> None:
    """Eight fixtures, 8192, one attempt each, no retry parameter."""
    from capture_harness import BASELINE_OUTPUT_TOKENS

    subjects, manifest_path, identity = frozen(tmp_path)
    provider = RecordingProvider()
    captured = capture_all(
        subjects=subjects,
        provider=provider,
        session_for=fake_session,
        run_id="r",
        captured_at="t",
        transcripts_dir=tmp_path / "transcripts",
        captures_dir=tmp_path / "captures",
        manifest_path=manifest_path,
        expected_manifest_id=identity,
        import_module=available(),
    )

    assert BASELINE_OUTPUT_TOKENS == 8192
    assert len(captured) == 8
    assert provider.calls == 8
    assert {r.max_output_tokens for r in provider.requests} == {8192}
    assert not set(inspect.signature(capture_all).parameters) & {
        "retries",
        "retry",
        "attempts",
        "adapt",
        "on_failure",
        "subset",
        "only",
        "limit",
    }


def test_a_provider_refusal_during_capture_is_still_an_outcome(tmp_path: Path) -> None:
    """Readiness is a precondition. What the provider then does is the result."""
    from baseline_support import refusal

    subjects, manifest_path, identity = frozen(tmp_path)
    provider = RecordingProvider(outcomes={0: refusal(), 3: refusal()})

    captured = capture_all(
        subjects=subjects,
        provider=provider,
        session_for=fake_session,
        run_id="r",
        captured_at="t",
        transcripts_dir=tmp_path / "transcripts",
        captures_dir=tmp_path / "captures",
        manifest_path=manifest_path,
        expected_manifest_id=identity,
        import_module=available(),
    )

    assert provider.calls == 8
    assert sum(1 for item in captured if not item.answered) == 2
    assert len(artifacts(tmp_path)) == 16
    for path in (tmp_path / "transcripts").glob("*.json"):
        assert json.loads(path.read_text(encoding="utf-8"))["provenance"] == "model"
