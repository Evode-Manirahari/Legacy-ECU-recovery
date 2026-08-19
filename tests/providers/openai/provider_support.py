"""Deterministic stand-ins for the OpenAI client.

The reply is not reproducible and is not meant to be - that is why a baseline
gets frozen. What *is* reproducible is everything this node owns: which
arguments go out, how many times, what comes back as a `ModelResponse`, and
which faults arrive as `ModelUnavailableError`. All of it is provable without a
network, an account, or the SDK installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeOutputDetails:
    reasoning_tokens: int = 0


@dataclass
class FakeUsage:
    input_tokens: int = 11
    output_tokens: int = 22
    output_tokens_details: Any = field(default_factory=FakeOutputDetails)

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        del mode
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}


@dataclass
class FakeIncomplete:
    reason: str = "max_output_tokens"


@dataclass
class FakeRawResponse:
    """Shaped like a Responses API result, carrying only what the adapter reads."""

    output_text: str = "the reply"
    model: str = "gpt-snapshot-2026-01-01"
    id: str = "resp_abc123"
    status: str = "completed"
    incomplete_details: Any = None
    usage: Any = field(default_factory=FakeUsage)


class FakeResponses:
    def __init__(self, owner: FakeClient) -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> Any:
        self._owner.calls.append(dict(kwargs))
        if self._owner.raises is not None:
            raise self._owner.raises
        return self._owner.reply


class FakeClient:
    """Records outbound calls, and whether one-attempt was enforced on it."""

    def __init__(self, reply: Any | None = None, raises: BaseException | None = None) -> None:
        self.reply = FakeRawResponse() if reply is None else reply
        self.raises = raises
        self.calls: list[dict[str, Any]] = []
        self.option_calls: list[dict[str, Any]] = []
        self.responses = FakeResponses(self)

    def with_options(self, **kwargs: Any) -> FakeClient:
        self.option_calls.append(dict(kwargs))
        return self


class OptionlessClient:
    """A client with no `with_options`, to prove the adapter tolerates one."""

    def __init__(self, reply: Any | None = None) -> None:
        self.reply = FakeRawResponse() if reply is None else reply
        self.calls: list[dict[str, Any]] = []
        self.responses = FakeResponses(self)  # type: ignore[arg-type]
        self.raises: BaseException | None = None
