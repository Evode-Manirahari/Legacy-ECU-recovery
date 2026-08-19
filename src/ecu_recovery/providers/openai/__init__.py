"""OpenAI transport, importable without the SDK installed.

Importing this package must never import `openai`; the adapter defers that to
the call that needs it, so the suite stays green on a host with no extra and no
key. See `adapter` for why retries are off.
"""

from __future__ import annotations

from .adapter import (
    API_KEY_VARIABLE,
    DEFAULT_TIMEOUT_SECONDS,
    MODEL_VARIABLE,
    PROVIDER_NAME,
    OpenAIProvider,
    provider_from_environment,
)

__all__ = [
    "API_KEY_VARIABLE",
    "DEFAULT_TIMEOUT_SECONDS",
    "MODEL_VARIABLE",
    "PROVIDER_NAME",
    "OpenAIProvider",
    "provider_from_environment",
]
