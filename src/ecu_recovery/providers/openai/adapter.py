"""OpenAI transport for the agent's model boundary.

`ModelRequest` in, `ModelResponse` out, and nothing else. This module does not
gather facts, parse replies, check citations, or score anything: `AGENT-001`
owns that path and is already verified, which is why this lives outside it. A
provider must not be able to reach into the reasoning it feeds.

Two properties here are load-bearing rather than stylistic.

The SDK is imported inside the call that needs it. `src/ecu_recovery` must stay
importable, and the whole suite green, on a machine with no `openai` installed
and no key set - the same arrangement Ghidra already has.

Retries are off. The official client retries twice by default, so an adapter
that simply does not mention retries sends up to three outbound requests while
the transcript records one. A capture taken that way is the best of several
tries wearing the label of a single attempt.
"""

from __future__ import annotations

import os
from typing import Any

from ...agent.provider import ModelRequest, ModelResponse, ModelUnavailableError

#: The only place a credential is read from. Never a constructor argument,
#: never a file, never a literal.
API_KEY_VARIABLE = "OPENAI_API_KEY"

#: Where a model identifier may be configured. There is deliberately no default:
#: this project does not name a snapshot it has not seen the API report.
MODEL_VARIABLE = "OPENAI_MODEL"

PROVIDER_NAME = "openai"

#: Generous, because a timeout is not retried here. A capture that dies at the
#: deadline is a lost sample, not a slow one.
DEFAULT_TIMEOUT_SECONDS = 300.0


def _single_attempt(client: Any) -> Any:
    """Force one outbound attempt, whoever built the client.

    Applied to injected clients too. A caller handing in a client configured
    elsewhere should not be able to reintroduce hidden retries by accident, and
    the invariant belongs to this adapter rather than to its callers.
    """
    with_options = getattr(client, "with_options", None)
    if with_options is None:
        return client
    return with_options(max_retries=0)


def _redact(text: str) -> str:
    """Remove the API key from anything about to be raised or recorded.

    A provider fault message can carry request context, and a transcript is
    committed. The key is read fresh rather than stored so that this is the only
    moment it exists in this module.
    """
    key = os.environ.get(API_KEY_VARIABLE, "")
    if key and key in text:
        text = text.replace(key, "[redacted]")
    return text


def _describe(error: BaseException) -> str:
    """Render a provider fault as one line, with no credential in it."""
    detail = str(error).strip()
    name = type(error).__name__
    return _redact(f"{name}: {detail}" if detail else name)


def _text_of(raw: Any) -> str:
    """Pull the reply text out, preferring the SDK's own accessor."""
    text = getattr(raw, "output_text", None)
    if isinstance(text, str):
        return text
    collected: list[str] = []
    for item in getattr(raw, "output", None) or ():
        for part in getattr(item, "content", None) or ():
            value = getattr(part, "text", None)
            if isinstance(value, str):
                collected.append(value)
    return "".join(collected)


def _plain(value: Any) -> Any:
    """Reduce an SDK object to something a frozen transcript can hold."""
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except TypeError:
            return dump()
    return value


def _incomplete_reason(raw: Any) -> str:
    details = getattr(raw, "incomplete_details", None)
    return str(getattr(details, "reason", "") or "")


class OpenAIProvider:
    """`ModelProvider` over the OpenAI Responses API.

    The model is handed instructions and a rendered fact sheet, and returns
    text. It gets no tools, no web access, no file access, and no store: the
    facts were already gathered deterministically, which is what keeps a wrong
    answer attributable to interpretation rather than to lookup.
    """

    name = PROVIDER_NAME

    def __init__(
        self,
        model: str,
        client: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """`model` is required. `client` is for tests; production builds its own.

        There is no `api_key` parameter, so there is no way to pass one. The key
        is read from the environment at call time and never held on the instance.
        """
        identifier = (model or "").strip()
        if not identifier:
            raise ModelUnavailableError(
                f"no model identifier was given; pass model= or set {MODEL_VARIABLE}"
            )
        self.model = identifier
        self._timeout = timeout
        self._client: Any | None = None if client is None else _single_attempt(client)

    def _resolve_client(self) -> Any:
        if self._client is not None:
            return self._client
        key = os.environ.get(API_KEY_VARIABLE, "").strip()
        if not key:
            raise ModelUnavailableError(
                f"{API_KEY_VARIABLE} is not set; export it to reach the provider"
            )
        try:
            from openai import OpenAI
        except ImportError as error:
            raise ModelUnavailableError(
                "the openai extra is not installed; run `uv sync --extra openai`"
            ) from error
        self._client = _single_attempt(OpenAI(api_key=key, max_retries=0, timeout=self._timeout))
        return self._client

    def complete(self, request: ModelRequest) -> ModelResponse:
        """One outbound request. Every fault leaves as `ModelUnavailableError`.

        The blanket catch is deliberate: `investigate` records a provider
        failure as an outcome rather than crashing a run, and it can only do
        that if transport faults arrive through the declared boundary. Which
        fault it was survives in the message and the chained cause.
        """
        client = self._resolve_client()
        try:
            raw = client.responses.create(
                model=self.model,
                instructions=request.instructions,
                input=request.context,
                max_output_tokens=request.max_output_tokens,
                store=False,
                stream=False,
            )
        except Exception as error:
            raise ModelUnavailableError(_describe(error)) from error
        return self._to_response(raw)

    def _to_response(self, raw: Any) -> ModelResponse:
        text = _text_of(raw)
        returned = str(getattr(raw, "model", "") or "")
        status = str(getattr(raw, "status", "") or "")
        reason = _incomplete_reason(raw)
        if not text.strip():
            raise ModelUnavailableError(
                f"the provider returned no text (status {status or 'unknown'})"
            )
        return ModelResponse(
            text=text,
            provider=PROVIDER_NAME,
            # The identifier the API reports, not the one asked for. An alias
            # resolves to a snapshot server-side, and what gets certified must
            # be what actually answered.
            model=returned or self.model,
            truncated=status == "incomplete" or reason == "max_output_tokens",
            metadata={
                "requested_model": self.model,
                "returned_model": returned,
                "model_identity_confirmed": bool(returned),
                "response_id": str(getattr(raw, "id", "") or ""),
                "status": status,
                "incomplete_reason": reason,
                "usage": _plain(getattr(raw, "usage", None)),
            },
        )


def provider_from_environment(
    model: str | None = None,
    client: Any | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> OpenAIProvider:
    """Build a provider from configuration rather than from a literal.

    No default model is supplied. `BASELINE-AGENT-001` must record the exact
    identifier it certified, and a default sitting here would be a name nobody
    checked the API for.
    """
    resolved = (model or os.environ.get(MODEL_VARIABLE, "")).strip()
    if not resolved:
        raise ModelUnavailableError(
            f"no model identifier; pass model= or set {MODEL_VARIABLE}. "
            "This project pins no default, so nothing is assumed about what answered."
        )
    return OpenAIProvider(model=resolved, client=client, timeout=timeout)
