"""Doubles for the baseline harness tests.

The whole eight-fixture path runs here with no network, no key, and no Ghidra.
That is the point rather than a compromise: everything the harness promises —
coverage, the ceiling, one attempt, freezing what came back — is a property of
the harness, not of the provider, and a property provable only by spending money
is not one anybody will check twice.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

from agent_support import FakeSession  # noqa: E402

from ecu_recovery.agent import ModelRequest, ModelResponse, ModelUnavailableError  # noqa: E402

#: The one function every FakeSession knows about. Subjects in a real manifest
#: are chosen per fixture; here one address stands in for all eight, because
#: what is under test is the harness rather than the dataset.
FAKE_SUBJECT = "0x1000"

GOOD_REPLY = json.dumps(
    {
        "claims": [
            {
                "statement": "the function increments its first argument",
                "support": "unknown",
                "confidence": 0.4,
                "citations": [],
            }
        ]
    }
)


@dataclass
class RecordingProvider:
    """A provider that records every request and answers however a test says.

    `outcomes` maps a call ordinal to what should happen: a string is returned
    as a reply, an exception is raised. Anything unlisted gets `GOOD_REPLY`.
    """

    name: str = "openai"
    model: str = "gpt-snapshot-2026-05-05"
    outcomes: dict[int, Any] = field(default_factory=dict)
    requests: list[ModelRequest] = field(default_factory=list)
    truncate: set[int] = field(default_factory=set)

    @property
    def calls(self) -> int:
        return len(self.requests)

    def complete(self, request: ModelRequest) -> ModelResponse:
        ordinal = len(self.requests)
        self.requests.append(request)
        outcome = self.outcomes.get(ordinal, GOOD_REPLY)
        if isinstance(outcome, Exception):
            raise outcome
        truncated = ordinal in self.truncate
        return ModelResponse(
            text=str(outcome),
            provider=self.name,
            model=self.model,
            truncated=truncated,
            metadata={
                "requested_model": "an-alias",
                "returned_model": self.model,
                "model_identity_confirmed": True,
                "response_id": f"resp_baseline_{ordinal}",
                "status": "incomplete" if truncated else "completed",
                "incomplete_reason": "max_output_tokens" if truncated else "",
                "usage": {
                    "input_tokens": 1000 + ordinal,
                    "output_tokens": 40 + ordinal,
                    "output_tokens_details": {"reasoning_tokens": 30 + ordinal},
                },
                # Fields no allowlist names, planted on every call.
                "api_key": SECRET,
                "authorization": f"Bearer {SECRET}",
                "organization": "org-should-never-appear",
            },
        )


#: A credential-shaped value, returned by the double on every call.
SECRET = "sk-proj-BaselineHarnessMustNeverFreezeThis"


def refusal() -> ModelUnavailableError:
    return ModelUnavailableError("the provider refused: 429 rate limit reached")


@contextmanager
def fake_session(sample_id: str) -> Iterator[FakeSession]:
    """A session factory with no Ghidra behind it."""
    del sample_id
    yield FakeSession()


def subjects_for(samples: tuple[str, ...]) -> dict[str, str]:
    return {sample_id: FAKE_SUBJECT for sample_id in samples}


def subject_manifest_body(subjects: dict[str, str]) -> dict[str, Any]:
    """The content a manifest identity is computed over."""
    return {
        "schema_version": 1,
        "dataset_id": "legacy_ecu_synthetic_v1",
        "subjects": dict(sorted(subjects.items())),
    }


def write_subject_manifest(
    path: Path,
    subjects: dict[str, str],
    indent: int | None = 2,
    sort_keys: bool = True,
    stamp_identity: bool = True,
) -> str:
    """Freeze a manifest and return its identity.

    The formatting arguments exist so a test can write the same content two
    different ways and check that the identity does not move. That is the whole
    reason for canonicalising before hashing.
    """
    from capture_harness import manifest_body, manifest_id

    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = dict(subject_manifest_body(subjects))
    if stamp_identity:
        payload["manifest_id"] = manifest_id(manifest_body(payload))
    path.write_text(
        json.dumps(payload, indent=indent, sort_keys=sort_keys) + "\n", encoding="utf-8"
    )
    return manifest_id(manifest_body(payload))
