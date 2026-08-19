"""What the OpenAI adapter must do, proved without a network.

Grouped by the property each test defends, because the contract's requirements
are what will be reviewed - not the method list.
"""

from __future__ import annotations

import builtins
import importlib
import sys
from typing import Any

import pytest
from provider_support import FakeClient, FakeIncomplete, FakeRawResponse, OptionlessClient

from ecu_recovery.agent.provider import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelUnavailableError,
)
from ecu_recovery.providers.openai import (
    API_KEY_VARIABLE,
    MODEL_VARIABLE,
    OpenAIProvider,
    provider_from_environment,
)

REQUEST = ModelRequest(instructions="interpret the facts", context="a fact sheet")


@pytest.fixture(autouse=True)
def _no_ambient_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let a developer's real key or model leak into a test."""
    monkeypatch.delenv(API_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(MODEL_VARIABLE, raising=False)


# --- the protocol is unchanged and unwidened ---


def test_the_adapter_satisfies_the_existing_protocol() -> None:
    assert isinstance(OpenAIProvider(model="m", client=FakeClient()), ModelProvider)


def test_it_returns_the_protocol_response_type() -> None:
    provider = OpenAIProvider(model="m", client=FakeClient())

    assert isinstance(provider.complete(REQUEST), ModelResponse)


# --- no new capability for the model ---


def test_the_request_grants_no_tools_and_no_streaming() -> None:
    """The whole point of the design: facts in, text out.

    A tools argument here would hand retrieval back to the model and make a
    wrong answer unattributable.
    """
    client = FakeClient()

    OpenAIProvider(model="a-model", client=client).complete(REQUEST)

    sent = client.calls[0]
    assert "tools" not in sent
    assert "tool_choice" not in sent
    assert sent["stream"] is False
    assert sent["store"] is False


def test_the_request_carries_the_configured_model_and_the_prompt_halves() -> None:
    client = FakeClient()

    OpenAIProvider(model="a-model", client=client).complete(REQUEST)

    sent = client.calls[0]
    assert sent["model"] == "a-model"
    assert sent["instructions"] == REQUEST.instructions
    assert sent["input"] == REQUEST.context
    assert sent["max_output_tokens"] == REQUEST.max_output_tokens


# --- one attempt means one attempt ---


def test_retries_are_disabled_on_an_injected_client() -> None:
    """The SDK retries twice by default, so silence here would mean three calls."""
    client = FakeClient()

    OpenAIProvider(model="m", client=client)

    assert client.option_calls == [{"max_retries": 0}]


def test_a_successful_call_goes_out_exactly_once() -> None:
    client = FakeClient()

    OpenAIProvider(model="m", client=client).complete(REQUEST)

    assert len(client.calls) == 1


def test_a_failing_call_is_not_retried() -> None:
    client = FakeClient(raises=TimeoutError("deadline exceeded"))
    provider = OpenAIProvider(model="m", client=client)

    with pytest.raises(ModelUnavailableError):
        provider.complete(REQUEST)

    assert len(client.calls) == 1


def test_a_client_without_with_options_still_works() -> None:
    client = OptionlessClient()

    OpenAIProvider(model="m", client=client).complete(REQUEST)

    assert len(client.calls) == 1


# --- the exact model identity is recorded ---


def test_the_returned_identifier_is_recorded_not_the_requested_one() -> None:
    """An alias resolves server-side; what gets certified must be what answered."""
    client = FakeClient(reply=FakeRawResponse(model="gpt-snapshot-2026-05-05"))

    response = OpenAIProvider(model="an-alias", client=client).complete(REQUEST)

    assert response.model == "gpt-snapshot-2026-05-05"
    assert response.metadata["requested_model"] == "an-alias"
    assert response.metadata["returned_model"] == "gpt-snapshot-2026-05-05"
    assert response.metadata["model_identity_confirmed"] is True


def test_an_unreported_identity_is_flagged_rather_than_assumed() -> None:
    client = FakeClient(reply=FakeRawResponse(model=""))

    response = OpenAIProvider(model="an-alias", client=client).complete(REQUEST)

    assert response.model == "an-alias"
    assert response.metadata["model_identity_confirmed"] is False


def test_the_response_carries_provenance_a_transcript_can_freeze() -> None:
    response = OpenAIProvider(model="m", client=FakeClient()).complete(REQUEST)

    assert response.provider == "openai"
    assert response.metadata["response_id"] == "resp_abc123"
    assert response.metadata["usage"] == {"input_tokens": 11, "output_tokens": 22}


def test_truncation_is_reported_rather_than_hidden() -> None:
    client = FakeClient(
        reply=FakeRawResponse(status="incomplete", incomplete_details=FakeIncomplete())
    )

    response = OpenAIProvider(model="m", client=client).complete(REQUEST)

    assert response.truncated is True
    assert response.metadata["incomplete_reason"] == "max_output_tokens"


# --- failure is a value ---


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timed out"),
        ConnectionError("connection reset"),
        RuntimeError("429 rate limit reached"),
        ValueError("500 internal server error"),
    ],
)
def test_every_transport_fault_arrives_through_the_declared_boundary(error: Exception) -> None:
    """`investigate` records a provider failure instead of crashing, but only
    if faults reach it as `ModelUnavailableError`."""
    provider = OpenAIProvider(model="m", client=FakeClient(raises=error))

    with pytest.raises(ModelUnavailableError) as raised:
        provider.complete(REQUEST)

    assert type(error).__name__ in str(raised.value)
    assert raised.value.__cause__ is error


def test_an_empty_reply_is_a_failure_not_an_answer() -> None:
    client = FakeClient(reply=FakeRawResponse(output_text="   "))
    provider = OpenAIProvider(model="m", client=client)

    with pytest.raises(ModelUnavailableError, match="no text"):
        provider.complete(REQUEST)


# --- no credential ever reaches disk or a log ---


def test_the_key_is_never_stored_on_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_VARIABLE, "sk-secret-value")

    provider = OpenAIProvider(model="m", client=FakeClient())

    assert "sk-secret-value" not in repr(vars(provider))


def test_a_fault_quoting_the_key_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider errors can echo request context, and a transcript is committed."""
    monkeypatch.setenv(API_KEY_VARIABLE, "sk-secret-value")
    client = FakeClient(raises=RuntimeError("rejected key sk-secret-value in header"))
    provider = OpenAIProvider(model="m", client=client)

    with pytest.raises(ModelUnavailableError) as raised:
        provider.complete(REQUEST)

    assert "sk-secret-value" not in str(raised.value)
    assert "[redacted]" in str(raised.value)


def test_there_is_no_way_to_pass_a_key_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_VARIABLE, "sk-secret-value")

    with pytest.raises(TypeError):
        OpenAIProvider(model="m", api_key="sk-other")  # type: ignore[call-arg]


# --- the suite runs with nothing configured ---


def test_a_missing_key_is_a_stated_refusal() -> None:
    provider = OpenAIProvider(model="m")

    with pytest.raises(ModelUnavailableError, match=API_KEY_VARIABLE):
        provider.complete(REQUEST)


def test_a_missing_extra_names_the_command_that_fixes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_VARIABLE, "sk-secret-value")
    real_import = builtins.__import__

    def blocked(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "openai" or name.startswith("openai."):
            raise ImportError("no module named openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    provider = OpenAIProvider(model="m")

    with pytest.raises(ModelUnavailableError, match="--extra openai"):
        provider.complete(REQUEST)


def test_the_package_imports_with_the_sdk_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves the SDK import is deferred, not merely absent from this host.

    Without this, a top-level `import openai` would pass here only because the
    extra happens to be uninstalled, and would break every contributor the day
    it was installed.
    """
    real_import = builtins.__import__

    def blocked(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "openai" or name.startswith("openai."):
            raise ImportError("no module named openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    for module in [name for name in sys.modules if name.startswith("ecu_recovery.providers")]:
        monkeypatch.delitem(sys.modules, module, raising=False)

    reimported = importlib.import_module("ecu_recovery.providers.openai")

    assert reimported.OpenAIProvider is not None


# --- the model identifier is configured, never invented ---


def test_no_default_model_is_pinned_anywhere() -> None:
    """`BASELINE-AGENT-001` must record what it certified. A default sitting
    here would be a snapshot name nobody asked the API for."""
    with pytest.raises(ModelUnavailableError, match=MODEL_VARIABLE):
        provider_from_environment()


def test_the_model_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_VARIABLE, "a-configured-model")

    assert provider_from_environment(client=FakeClient()).model == "a-configured-model"


def test_an_explicit_model_wins_over_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_VARIABLE, "from-env")

    provider = provider_from_environment(model="explicit", client=FakeClient())

    assert provider.model == "explicit"


def test_a_blank_model_is_refused() -> None:
    with pytest.raises(ModelUnavailableError):
        OpenAIProvider(model="   ")
