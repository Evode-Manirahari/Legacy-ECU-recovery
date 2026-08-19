"""The model boundary, deliberately provider-agnostic.

No SDK, no HTTP client, no vendor types, and no dependency added to the project.
`ModelProvider` is a protocol with one method; a real adapter is a separate,
separately-authorized piece of work, and until it exists this interface is
exercised entirely by test doubles.

That is not a limitation to apologise for. Everything interesting about this
node - what facts get gathered, how they are rendered, how a reply is parsed,
whether a citation survives checking - is deterministic and testable without any
model at all. Keeping the provider behind one narrow method is what makes that
possible, and it means the suite stays green with no API key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class ModelUnavailableError(RuntimeError):
    """No provider is configured, or the configured one cannot run."""


@dataclass(frozen=True)
class ModelRequest:
    """One call to a model, in terms no vendor owns.

    `instructions` is the standing task; `context` is the rendered fact sheet.
    They are separate because the fact sheet changes per function while the task
    does not, and a caller inspecting a transcript should be able to tell which
    part varied.
    """

    instructions: str
    context: str
    max_output_tokens: int = 2048

    def as_dict(self) -> dict[str, Any]:
        return {
            "instructions": self.instructions,
            "context": self.context,
            "max_output_tokens": self.max_output_tokens,
        }


@dataclass(frozen=True)
class ModelResponse:
    """What came back. `text` is the whole of it: no tool calls, no side effects.

    The model is not given tools. It is given facts that were already gathered
    and asked to interpret them, which is what keeps retrieval deterministic and
    keeps a wrong answer attributable to interpretation rather than to lookup.
    """

    text: str
    provider: str = "unknown"
    model: str = "unknown"
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ModelProvider(Protocol):
    """One method. Anything satisfying this can be injected."""

    name: str

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Return the model's reply, or raise `ModelUnavailableError`."""
        ...


class UnconfiguredProvider:
    """The default. Refuses clearly rather than pretending to be a model.

    Present so that constructing an investigator without a provider is legal and
    the deterministic half stays reachable; only the interpretation step fails,
    and it fails with a sentence that says what to do about it.
    """

    name = "unconfigured"

    def complete(self, request: ModelRequest) -> ModelResponse:
        del request
        raise ModelUnavailableError(
            "no model provider is configured; inject one implementing ModelProvider. "
            "A real provider adapter is authorized separately from AGENT-001."
        )
