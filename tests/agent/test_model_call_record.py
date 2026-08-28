"""What a transcript records about the call that produced it.

The transport already returned all of this. `investigate` kept the provider name
and the model name and dropped the rest before anything was frozen, so a
committed transcript could not say which snapshot answered, under what ceiling,
whether the reply was cut off, or what it cost. These tests pin the record that
closes that gap, and pin its two hard edges: nothing outside a named allowlist
gets in, and nothing that varies between two identical runs gets in either.

No provider SDK, no key, no network. The boundary is one method.
"""

from __future__ import annotations

import json
from typing import Any

from agent_support import SUBJECT, ScriptedProvider, fake_context, unavailable_provider

from ecu_recovery.agent import InvestigationBudget, investigate
from ecu_recovery.agent.models import ModelCall

#: A credential-shaped value, planted in fields no allowlist names.
SECRET = "sk-proj-ThisMustNeverReachAnArtifact0123456789"

#: Exactly what a frozen call record may contain. Stated in full rather than
#: checked field by field: the failure this guards against is a field arriving
#: that nobody decided to record, and only a complete comparison sees one.
RECORD_FIELDS = {
    "provider",
    "requested_model",
    "returned_model",
    "model_identity_confirmed",
    "response_id",
    "status",
    "incomplete_reason",
    "truncated",
    "max_output_tokens",
    "usage",
    "reasoning_tokens",
    "request_digest",
    "reply_digest",
    "failure",
}

REPLY = json.dumps(
    {
        "claims": [
            {
                "statement": "the function increments its argument",
                "support": "unknown",
                "confidence": 0.4,
                "citations": [],
            }
        ]
    }
)


def full_metadata(**overrides: object) -> dict[str, object]:
    """The metadata shape the OpenAI adapter returns, plus fields it never does."""
    metadata: dict[str, object] = {
        "requested_model": "an-alias",
        "returned_model": "gpt-snapshot-2026-05-05",
        "model_identity_confirmed": True,
        "response_id": "resp_abc123",
        "status": "completed",
        "incomplete_reason": "",
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 350,
            "total_tokens": 1550,
            "output_tokens_details": {"reasoning_tokens": 280},
            "input_tokens_details": {"cached_tokens": 1024},
        },
    }
    metadata.update(overrides)
    return metadata


def answered(**overrides: object) -> ScriptedProvider:
    return ScriptedProvider(
        reply=REPLY,
        name="openai",
        model="gpt-snapshot-2026-05-05",
        metadata=full_metadata(**overrides),
    )


def record_of(
    provider: ScriptedProvider, budget: InvestigationBudget | None = None
) -> dict[str, Any]:
    investigation = investigate(fake_context(), SUBJECT, provider=provider, budget=budget)
    call = investigation.as_dict()["model_call"]
    assert isinstance(call, dict)
    return call


# --- the record exists, and it is complete ---


def test_the_frozen_record_names_what_produced_the_reply() -> None:
    """Every field the transport returned, and the ceiling it was given."""
    call = record_of(answered(), InvestigationBudget(max_output_tokens=4096))

    assert call["provider"] == "openai"
    assert call["requested_model"] == "an-alias"
    assert call["returned_model"] == "gpt-snapshot-2026-05-05"
    assert call["model_identity_confirmed"] is True
    assert call["response_id"] == "resp_abc123"
    assert call["status"] == "completed"
    assert call["max_output_tokens"] == 4096
    assert call["truncated"] is False
    assert call["usage"]["input_tokens"] == 1200
    assert call["usage"]["output_tokens"] == 350
    assert call["reasoning_tokens"] == 280
    assert len(call["request_digest"]) == 64
    assert len(call["reply_digest"]) == 64


def test_the_requested_and_returned_identifiers_stay_distinguishable() -> None:
    """An alias resolves server-side, and both halves of that matter.

    What answered is what gets certified; what was asked for is what a rerun
    would ask for again. Collapsing them into one string loses whichever
    question is being asked later.
    """
    call = record_of(answered())

    assert call["requested_model"] != call["returned_model"]


def test_an_unconfirmed_identity_is_recorded_as_unconfirmed() -> None:
    call = record_of(answered(returned_model="", model_identity_confirmed=False))

    assert call["model_identity_confirmed"] is False
    assert call["returned_model"] == "gpt-snapshot-2026-05-05"  # the response's own field


def test_truncation_reaches_the_transcript() -> None:
    provider = answered(status="incomplete", incomplete_reason="max_output_tokens")
    provider.truncated = True

    call = record_of(provider)

    assert call["truncated"] is True
    assert call["incomplete_reason"] == "max_output_tokens"


# --- a failure is still evidence ---


def test_a_transport_failure_still_records_what_was_attempted() -> None:
    """A lost sample should say what was tried, not be a blank."""
    call = record_of(unavailable_provider(), InvestigationBudget(max_output_tokens=777))

    assert call["provider"] == "scripted"
    assert call["max_output_tokens"] == 777
    assert len(call["request_digest"]) == 64
    assert call["reply_digest"] == ""
    assert "no key configured" in call["failure"]


def test_a_reply_that_could_not_be_parsed_is_still_a_call_that_answered() -> None:
    """The provider answered; the answer was unusable. Two different facts.

    Recording this as a transport failure would throw away a real sample and the
    response id that makes it auditable.
    """
    call = record_of(
        ScriptedProvider(reply="not json at all", name="openai", metadata=full_metadata())
    )

    assert call["response_id"] == "resp_abc123"
    assert call["reply_digest"] != ""
    assert "unusable reply" in call["failure"]


# --- the allowlist ---


def test_only_named_fields_reach_the_frozen_record() -> None:
    call = record_of(answered())

    assert set(call) == RECORD_FIELDS


def test_no_credential_or_header_survives_serialization() -> None:
    """The guarantee is the allowlist, not a redactor.

    A redactor has to recognise a secret to remove one, so it covers the shapes
    somebody thought of. Copying only named fields cannot leak a field nobody
    named, whatever the next provider decides to return.
    """
    provider = answered(
        api_key=SECRET,
        authorization=f"Bearer {SECRET}",
        organization="org-private",
        project="proj-private",
        headers={"x-api-key": SECRET},
        _request={"api_key": SECRET},
    )

    investigation = investigate(fake_context(), SUBJECT, provider=provider)
    rendered = json.dumps(investigation.as_dict())

    assert SECRET not in rendered
    assert "org-private" not in rendered
    assert "proj-private" not in rendered
    assert "x-api-key" not in rendered


def test_a_secret_hidden_inside_usage_does_not_survive_either() -> None:
    """Usage is copied counter by counter, not as an object."""
    provider = answered(
        usage={"input_tokens": 10, "output_tokens": 2, "api_key": SECRET, "account": "acct-1"}
    )

    call = record_of(provider)

    assert call["usage"] == {"input_tokens": 10, "output_tokens": 2}
    assert SECRET not in json.dumps(call)


def test_a_usage_counter_that_is_not_a_number_is_dropped() -> None:
    """Better absent than recorded as the repr of whatever arrived."""
    call = record_of(answered(usage={"input_tokens": "lots", "output_tokens": 4}))

    assert call["usage"] == {"output_tokens": 4}


def test_a_boolean_is_not_a_token_count() -> None:
    call = record_of(answered(usage={"input_tokens": True, "output_tokens": 4}))

    assert call["usage"] == {"output_tokens": 4}


def test_missing_usage_is_an_empty_record_rather_than_an_invention() -> None:
    call = record_of(answered(usage=None))

    assert call["usage"] == {}
    assert call["reasoning_tokens"] is None


# --- determinism ---


def test_the_same_investigation_serializes_identically_twice() -> None:
    """A transcript is compared and re-scored, so it may not vary by occasion."""
    first = investigate(fake_context(), SUBJECT, provider=answered()).as_dict()
    second = investigate(fake_context(), SUBJECT, provider=answered()).as_dict()

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_no_wall_clock_or_run_identity_is_in_the_agent_record() -> None:
    """Those belong to the capture record, which is a separate artifact.

    Putting them here would make two identical investigations serialize
    differently, and a transcript that cannot be compared cannot be a control.
    """
    call = record_of(answered())

    for forbidden in ("captured_at", "timestamp", "run_id", "created", "created_at", "elapsed"):
        assert forbidden not in call


def test_the_request_digest_follows_the_request_and_nothing_else() -> None:
    narrow = record_of(answered(), InvestigationBudget(max_output_tokens=64))
    wide = record_of(answered(), InvestigationBudget(max_output_tokens=65))

    assert narrow["request_digest"] != wide["request_digest"]


def test_an_investigation_without_a_provider_records_no_call_it_did_not_make() -> None:
    """`UnconfiguredProvider` fails before a request goes anywhere."""
    investigation = investigate(fake_context(), SUBJECT)
    call = investigation.as_dict()["model_call"]

    assert call is not None
    assert call["provider"] == "unconfigured"
    assert call["response_id"] == ""
    assert "no model provider is configured" in call["failure"]


def test_the_record_is_an_object_a_capture_can_hold() -> None:
    """Round-trips through JSON unchanged, which is what freezing requires."""
    call = ModelCall(provider="openai", requested_model="m", max_output_tokens=8)

    assert json.loads(json.dumps(call.as_dict())) == call.as_dict()
