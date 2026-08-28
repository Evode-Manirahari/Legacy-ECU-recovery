"""Capture records: what a call was, frozen beside what it said.

A transcript is what the model replied. A capture record is what the provider
did to produce that reply, written at capture time and never edited: the
provider, the identifier asked for and the identifier that answered, the
response id, the output ceiling in force, truncation state, usage, and digests
of the request and the reply.

The two are separate artifacts on purpose. A transcript is scored; a capture
record is checked. Keeping them apart is what lets the evaluator ask whether a
transcript's claim to be a real-model baseline is backed by anything.

## What a capture record proves, and what it does not

It proves **integrity and linkage**. The identifier is derived from the record's
own body, so editing a field and leaving the identifier alone is detectable, and
so is pointing a transcript at a record that was written for a different one.
Before this existed, `"provenance": "model"` typed into a file was accepted as a
real-model baseline; that is what this closes.

It does **not** prove that a provider made the call, and no artifact this
repository can hold would. A party who can write one file can write two
consistent ones. What changes is the cost and the shape of a forgery: it must
now be deliberate and internally consistent rather than a single word, and every
certified capture carries the **provider-issued response id** — the one field a
human can check against the provider's own account records.

So the result is a *verified baseline capture*: verified as an artifact, and
independently auditable through the response id by someone who looks. Anything
stronger would be a claim about a provider that this code is in no position to
make, and the gate contract requires those response ids to be published for
exactly that reason.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...agent.models import canonical_digest
from .transcripts import Transcript

CAPTURE_SCHEMA_VERSION = 1

#: Content-derived, like the evidence keys in the agent's own model, and for the
#: same reason: identity that follows what a thing *is* cannot be reassigned by
#: renaming it.
CAPTURE_ID_PREFIX = "C-"

#: A capture id reaches the filesystem, and it arrives from a transcript file.
#: Matching the exact shape before joining it to a path is what stops a
#: transcript naming `../../somewhere/else` from being opened.
CAPTURE_ID_PATTERN = re.compile(r"^C-[0-9a-f]{64}$")

#: The reply arrived, whether or not it turned out to be usable.
ANSWERED = "answered"
#: No reply arrived: a timeout, a refusal, an empty response, a transport fault.
FAILED = "failed"
OUTCOMES = (ANSWERED, FAILED)

#: Names that mean "no provider was involved". A capture claiming one of these
#: is honest about being scripted and cannot certify a real-model run.
UNREAL_PROVIDERS = frozenset({"", "unknown", "unconfigured", "scripted", "authored", "none"})

_BODY_FIELDS = ("transcript_id", "sample_id", "subject", "outcome", "run_id", "captured_at")


class CaptureError(ValueError):
    """A capture record is missing, malformed, or not what it claims to be."""


@dataclass(frozen=True)
class CaptureRecord:
    """One real call, recorded when it was made.

    `run_id` and `captured_at` live here rather than in the transcript. They are
    true of an occasion rather than of a call, and the agent's own serialization
    has to stay deterministic so that two identical investigations compare equal.
    """

    transcript_id: str
    sample_id: str
    subject: str
    outcome: str
    model_call: dict[str, Any] = field(default_factory=dict)
    #: Which capture session this came from. Free-form, and never part of what
    #: is verified beyond being covered by the identifier like everything else.
    run_id: str = ""
    #: Wall-clock, for auditing. It is not evidence of anything on its own.
    captured_at: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise CaptureError(f"outcome must be one of {OUTCOMES}, not {self.outcome!r}")
        if not self.transcript_id.strip():
            raise CaptureError("a capture record must name the transcript it belongs to")

    def body(self) -> dict[str, Any]:
        """Everything the identifier is derived from.

        The whole record, deliberately. A field left outside the digest is a
        field that can be changed without detection, so there is no such field.
        """
        return {
            "transcript_id": self.transcript_id,
            "sample_id": self.sample_id,
            "subject": self.subject,
            "outcome": self.outcome,
            "run_id": self.run_id,
            "captured_at": self.captured_at,
            "model_call": dict(self.model_call),
        }

    @property
    def capture_id(self) -> str:
        """Recomputed from the body every time it is asked for.

        Never stored on the instance and never read back from a file: an
        identifier that can be read from the artifact it identifies checks
        nothing.
        """
        return CAPTURE_ID_PREFIX + canonical_digest(self.body())

    def as_dict(self) -> dict[str, Any]:
        return {
            "capture_schema_version": CAPTURE_SCHEMA_VERSION,
            "capture_id": self.capture_id,
            "body": self.body(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CaptureRecord:
        body = payload.get("body")
        if not isinstance(body, dict):
            raise CaptureError("capture record has no body object")
        missing = [name for name in _BODY_FIELDS if name not in body]
        if missing:
            raise CaptureError(f"capture body is missing {missing}")
        call = body.get("model_call")
        if not isinstance(call, dict):
            raise CaptureError("capture body has no model_call object")
        return cls(
            transcript_id=str(body["transcript_id"]),
            sample_id=str(body["sample_id"]),
            subject=str(body["subject"]),
            outcome=str(body["outcome"]),
            model_call=dict(call),
            run_id=str(body["run_id"]),
            captured_at=str(body["captured_at"]),
        )


def record_for(
    transcript_id: str,
    sample_id: str,
    subject: str,
    investigation: dict[str, Any],
    run_id: str = "",
    captured_at: str = "",
) -> CaptureRecord:
    """Build the record for one completed investigation.

    The outcome follows the reply, not the verdict on it. A reply that arrived
    and could not be parsed is still a call the provider answered, and recording
    it as a failure would lose a real sample and the response id that makes it
    auditable.
    """
    call = investigation.get("model_call")
    if not isinstance(call, dict):
        raise CaptureError(f"{transcript_id}: the investigation records no model call")
    return CaptureRecord(
        transcript_id=transcript_id,
        sample_id=sample_id,
        subject=subject,
        outcome=ANSWERED if str(call.get("reply_digest", "")) else FAILED,
        model_call=dict(call),
        run_id=run_id,
        captured_at=captured_at,
    )


def write_capture(directory: Path, record: CaptureRecord) -> Path:
    """Write a record under its own identifier. Never overwrite a different one.

    Records are immutable. Writing the identical record twice is harmless — the
    identifier is content-derived, so it is the same record — but a file already
    standing under that name with different bytes means something is wrong that
    silently replacing it would hide.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.capture_id}.json"
    rendered = json.dumps(record.as_dict(), indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != rendered:
        raise CaptureError(f"a different capture record already stands at {path.name}")
    path.write_text(rendered, encoding="utf-8")
    return path


def load_capture(directory: Path, capture_id: str) -> CaptureRecord:
    """Read one record by identifier, refusing anything that is not one."""
    if not CAPTURE_ID_PATTERN.match(capture_id):
        raise CaptureError(f"{capture_id!r} is not a capture identifier")
    path = directory / f"{capture_id}.json"
    if not path.is_file():
        raise CaptureError(f"no capture record at {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(f"capture record {capture_id} is unreadable: {error}") from error
    if not isinstance(payload, dict):
        raise CaptureError(f"capture record {capture_id} is not an object")
    record = CaptureRecord.from_dict(payload)
    stated = str(payload.get("capture_id", ""))
    if stated != record.capture_id:
        raise CaptureError(
            f"capture record {capture_id} states id {stated!r} but its contents give "
            f"{record.capture_id!r}; it was edited after it was written"
        )
    return record


def verify_linkage(transcript: Transcript, directory: Path) -> str:
    """Check one transcript's claim to come from a real call.

    Returns the reason it does not hold, or an empty string when it does. A
    reason rather than a boolean, because a run that quietly declines to count a
    transcript is as hard to audit as one that quietly counts it.

    This can only ever refuse. Nothing here promotes a transcript to real-model
    provenance that did not arrive claiming it.
    """
    label = transcript.id
    if not transcript.capture_id:
        return f"{label}: claims model provenance and names no capture record"
    if not CAPTURE_ID_PATTERN.match(transcript.capture_id):
        return f"{label}: {transcript.capture_id!r} is not a capture identifier"

    try:
        record = load_capture(directory, transcript.capture_id)
    except CaptureError as error:
        return f"{label}: {error}"

    if record.capture_id != transcript.capture_id:
        return (
            f"{label}: capture record {transcript.capture_id} does not match its own contents; "
            f"recomputing gives {record.capture_id}, so it was edited after capture"
        )
    if record.transcript_id != transcript.id:
        return (
            f"{label}: capture record {record.capture_id} was written for "
            f"{record.transcript_id!r}, not for this transcript"
        )
    if record.sample_id != transcript.sample_id or record.subject != transcript.subject:
        return (
            f"{label}: capture record names sample {record.sample_id!r} subject "
            f"{record.subject!r}, and the transcript names {transcript.sample_id!r} / "
            f"{transcript.subject!r}"
        )

    call = transcript.investigation.get("model_call")
    if not isinstance(call, dict):
        return f"{label}: the transcript records no model call for the capture to attest"
    if call != record.model_call:
        return (
            f"{label}: the transcript's model call and capture record {record.capture_id} "
            "disagree; one of them was changed after the other was written"
        )

    provider = str(call.get("provider", "")).strip().lower()
    if provider in UNREAL_PROVIDERS:
        return f"{label}: capture names provider {provider!r}, which is not a real provider"
    if record.outcome == ANSWERED and not str(call.get("response_id", "")).strip():
        return (
            f"{label}: the capture carries no provider-issued response id, so nothing about it "
            "can be checked against the provider's own records"
        )
    return ""
