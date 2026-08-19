"""Checks against the real SDK, skipped when the extra is absent.

Everything else in this node is proved with fakes, which is the right default: a
fake cannot tell us the SDK still has the knobs the contract depends on. These
tests do, and they construct a client without calling it - construction is
local, so nothing here reaches the network or needs a real account.

They skip with a reason on a host without the extra, exactly as the Ghidra tests
do. A contributor with no OpenAI account still gets a green, honest run.
"""

from __future__ import annotations

import inspect

import pytest

from ecu_recovery.providers.openai import API_KEY_VARIABLE, OpenAIProvider


def openai_skip_reason() -> str | None:
    """Explain why the SDK checks cannot run, or `None` when they can."""
    try:
        import openai  # noqa: F401
    except ImportError:
        return "openai is not installed; run `uv sync --extra openai`"
    return None


requires_openai = pytest.mark.skipif(
    openai_skip_reason() is not None, reason=openai_skip_reason() or ""
)


@requires_openai
def test_the_client_this_adapter_builds_has_retries_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The invariant, on the real object rather than on a stand-in."""
    monkeypatch.setenv(API_KEY_VARIABLE, "sk-not-a-real-key")

    client = OpenAIProvider(model="a-model")._resolve_client()

    assert client.max_retries == 0


@requires_openai
def test_the_sdk_still_accepts_every_argument_the_contract_fixes() -> None:
    """An interface guard.

    The contract fixes `store=False`, no streaming, no tools, one attempt. If a
    future SDK renames or drops one of these, this fails here rather than
    halfway through a baseline capture.
    """
    from openai import OpenAI
    from openai.resources.responses import Responses

    assert "max_retries" in inspect.signature(OpenAI.__init__).parameters

    create = inspect.signature(Responses.create).parameters
    for argument in ("model", "instructions", "input", "max_output_tokens", "store", "stream"):
        assert argument in create, f"the SDK no longer accepts {argument!r}"


@requires_openai
def test_every_provider_fault_descends_from_one_base() -> None:
    """Why the blanket catch in `complete` is sound rather than lazy."""
    import openai

    for name in (
        "APITimeoutError",
        "APIConnectionError",
        "RateLimitError",
        "AuthenticationError",
        "InternalServerError",
        "BadRequestError",
    ):
        assert issubclass(getattr(openai, name), openai.OpenAIError)
