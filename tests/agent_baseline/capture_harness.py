"""The eight-fixture baseline capture: prepared, and inert until a human runs it.

This module performs the capture. It decides nothing about it. The subjects come
from a frozen manifest, the output ceiling is a module constant, and the model
identifier comes from the environment — so the three things that determine what
the first real baseline measures are all settled before this code runs, by
someone who can be asked why.

Four properties are structural rather than documented, because a rule the code
does not enforce is a comment:

**Coverage is not a parameter.** `capture_all` takes no fixture argument and no
subset. It validates the subject manifest against the committed dataset manifest
and refuses anything that is not exactly the eight samples. There is no way to
capture seven, and no way to capture the same seven twice and keep the better
run.

**The budget is a constant.** A ceiling that can be passed in is a ceiling that
can be raised after a disappointing answer, and the ceiling in force is part of
what the capture certifies.

**One attempt means one attempt.** `investigate` is called once per fixture and
its result is frozen. There is no retry, no second provider, no branch that
notices a poor answer. The adapter already forces `max_retries=0`; this is the
layer above making the same promise.

**Every outcome is frozen.** A refusal, a timeout, an empty reply, a truncated
reply, and an unparseable reply are all captured and committed. A baseline that
keeps only its successes is not a baseline.

Ground truth is never read here. The harness knows a sample id and a function
address; what the function *does* is what the model is being measured on, and it
arrives — if at all — from `REVIEW-AGENT-BASELINE-001`, after the freeze.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecu_recovery.agent import InvestigationBudget, investigate
from ecu_recovery.agent.models import canonical_digest
from ecu_recovery.evaluation.agent.captures import CaptureRecord, record_for, write_capture
from ecu_recovery.tools import ToolContext

REPO_ROOT = Path(__file__).resolve().parents[2]

#: DATA-001's dataset manifest. Committed, verified, and the authority on which
#: samples exist. Coverage is checked against this rather than against a list
#: retyped here, so a dataset that grows cannot leave the baseline behind.
DATASET_MANIFEST = REPO_ROOT / "samples" / "synthetic" / "manifest.json"
SAMPLES_ROOT = REPO_ROOT / "samples" / "synthetic" / "binaries"

BASELINE_ROOT = REPO_ROOT / "artifacts" / "agent-baseline"
SUBJECT_MANIFEST = BASELINE_ROOT / "results" / "subject-manifest.json"
TRANSCRIPTS_DIR = BASELINE_ROOT / "transcripts"
CAPTURES_DIR = BASELINE_ROOT / "captures"

#: Identity of the frozen subject manifest, recorded here rather than beside the
#: manifest itself. A file carrying its own expected digest attests to nothing;
#: keeping the two in different trees makes changing what gets captured a
#: two-file diff a reviewer sees.
#:
#: Frozen 2026-08-28, before any model was called and before any transcript
#: existed. It covers the canonical body of
#: `artifacts/agent-baseline/results/subject-manifest.json`: the schema version,
#: the selection rule, the weighting, the exclusion statement, and the eight
#: fixture-to-address pairs.
#:
#: An earlier value, `M-c940a1336f8af121ae6ba26e4a422de67bfaf7466b573dc0f88a666d8352515f`,
#: was superseded here. Its canonical body could not be reconstructed: 1,981
#: candidate serializations were tried across every degree of freedom that does
#: not touch the mapping - field sets, key names, orderings, address
#: representations, nesting, and rule wordings - and none reproduced it. A digest
#: whose preimage nobody can state verifies nothing, so it was replaced rather
#: than worked around.
#:
#: What was superseded is the digest, not the decision. The subject mapping is
#: byte-for-byte the frozen one and was verified independently of it: each
#: address is the function that fixture's `sample_probe` invokes, resolved from
#: the unstripped binaries outside this harness, and all eight matched. The
#: supersession happened before any spend, which is the only time it could have
#: happened honestly.
SUBJECT_MANIFEST_ID = "M-dd677b4a5603966052d08feb7de8e7f01d98a6186044ed7cea4fd93ecacd0248"

#: Manifest identity follows the convention already used for captures (`C-`) and
#: evidence keys (`E-`): a prefix on a digest of the *canonical body*, not of the
#: file's bytes.
#:
#: The distinction is the point. A byte digest changes when somebody reindents
#: the file or a tool reorders its keys, so it conflates "the frozen subjects
#: changed" with "the formatting changed" - and the first is the only one worth
#: refusing a capture over. Canonicalising first means the identifier answers
#: exactly one question: is this the same manifest content that was agreed?
MANIFEST_ID_PREFIX = "M-"
MANIFEST_ID_PATTERN = re.compile(r"^M-[0-9a-f]{64}$")

#: The field holding the identifier. Excluded from what is hashed, because a
#: value cannot be part of the digest that produces it.
MANIFEST_ID_FIELD = "manifest_id"

#: The output ceiling for every call in the baseline.
#:
#: `max_output_tokens` bounds reasoning as well as visible output, so a ceiling
#: sized for a JSON reply can be spent entirely on thinking and return nothing.
#: 8192 is stated here, once, and is part of every frozen record.
BASELINE_OUTPUT_TOKENS = 8192

SUBJECT_MANIFEST_SCHEMA = 1


class BaselinePreparationError(RuntimeError):
    """The capture cannot start, and says exactly what is missing."""


SessionFactory = Callable[[str], AbstractContextManager[Any]]


@dataclass(frozen=True)
class CapturedFixture:
    """One fixture, captured: the transcript written and the record behind it."""

    sample_id: str
    subject: str
    transcript_path: Path
    capture: CaptureRecord
    failure: str | None

    @property
    def answered(self) -> bool:
        return self.failure is None


def manifest_body(payload: dict[str, Any]) -> dict[str, Any]:
    """What the identifier covers: everything the manifest says except the identifier.

    Two layouts are accepted because both are reasonable and the frozen one is
    whichever a reviewer chose. A manifest nesting its content under `body`
    hashes that object; a flat manifest hashes itself with the identifier field
    removed. Either way the field carrying the identifier is outside the digest,
    since a value cannot be part of the digest that produces it.
    """
    nested = payload.get("body")
    if isinstance(nested, dict):
        return nested
    return {name: value for name, value in payload.items() if name != MANIFEST_ID_FIELD}


def manifest_id(body: dict[str, Any]) -> str:
    """The identity of a manifest body, independent of how it was written down."""
    return MANIFEST_ID_PREFIX + canonical_digest(body)


def dataset_samples() -> tuple[str, ...]:
    """Every sample the committed dataset manifest declares, in a stable order."""
    manifest = json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise BaselinePreparationError("unsupported synthetic manifest schema")
    return tuple(sorted(manifest["samples"]))


def load_subject_manifest(
    path: Path = SUBJECT_MANIFEST,
    expected_id: str = SUBJECT_MANIFEST_ID,
) -> dict[str, str]:
    """The frozen subject per fixture, or a refusal naming what is wrong.

    Every check here is a way the first baseline could otherwise measure
    something nobody chose: the manifest exists, its content reproduces the
    identity recorded away from it, its own stated identity agrees, it covers
    exactly the dataset's samples, and every subject is a non-empty address.
    """
    if not expected_id:
        raise BaselinePreparationError(
            "no subject manifest has been frozen: SUBJECT_MANIFEST_ID is unset. "
            "Freeze one subject per fixture and record its identity here before capturing."
        )
    if not MANIFEST_ID_PATTERN.match(expected_id):
        raise BaselinePreparationError(f"{expected_id!r} is not a manifest identifier")
    if not path.is_file():
        raise BaselinePreparationError(f"no subject manifest at {path}")

    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise BaselinePreparationError("subject manifest is not an object")

    computed = manifest_id(manifest_body(manifest))
    stated = str(manifest.get(MANIFEST_ID_FIELD, ""))
    if stated and stated != computed:
        raise BaselinePreparationError(
            f"subject manifest states identity {stated} but its contents give {computed}; "
            "it was edited after it was written"
        )
    if computed != expected_id:
        raise BaselinePreparationError(
            f"subject manifest {path.name} has identity {computed}, and {expected_id} was "
            "recorded; it changed after it was frozen, so what would be captured is not "
            "what was agreed"
        )

    body = manifest_body(manifest)
    if body.get("schema_version") != SUBJECT_MANIFEST_SCHEMA:
        raise BaselinePreparationError("unsupported subject manifest schema")
    subjects = body.get("subjects")
    if not isinstance(subjects, dict):
        raise BaselinePreparationError("subject manifest has no subjects object")

    expected = set(dataset_samples())
    missing = sorted(expected - set(subjects))
    extra = sorted(set(subjects) - expected)
    if missing or extra:
        raise BaselinePreparationError(
            f"subject manifest must name exactly the dataset's samples; missing {missing}, "
            f"unexpected {extra}"
        )
    for sample_id, subject in subjects.items():
        if not str(subject).strip():
            raise BaselinePreparationError(f"{sample_id}: no subject address")
    return {sample_id: str(subject) for sample_id, subject in sorted(subjects.items())}


def freeze_transcript(directory: Path, payload: dict[str, Any]) -> Path:
    """Write one transcript, and never quietly replace a different one.

    Rewriting identical bytes is harmless. A file already standing there with
    other contents means a capture is being run over the top of one that already
    happened, and silently replacing it would destroy the only record of what
    the first run produced.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{payload['id']}.json"
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != rendered:
        raise BaselinePreparationError(
            f"a different transcript already stands at {path.name}; a frozen capture is "
            "never overwritten"
        )
    path.write_text(rendered, encoding="utf-8")
    return path


def capture_one(
    sample_id: str,
    subject: str,
    context: ToolContext,
    provider: Any,
    run_id: str,
    captured_at: str,
    transcripts_dir: Path,
    captures_dir: Path,
) -> CapturedFixture:
    """One fixture, one call, whatever comes back.

    No branch here inspects the answer. A refusal, an empty reply, a truncated
    reply and a good one all take the same path to the same two files, which is
    what stops the capture from becoming a filter.
    """
    investigation = investigate(
        context,
        subject,
        provider=provider,
        budget=InvestigationBudget(max_output_tokens=BASELINE_OUTPUT_TOKENS),
    )
    payload = investigation.as_dict()
    transcript_id = f"baseline-{sample_id}"

    record = record_for(
        transcript_id=transcript_id,
        sample_id=sample_id,
        subject=subject,
        investigation=payload,
        run_id=run_id,
        captured_at=captured_at,
    )
    write_capture(captures_dir, record)

    transcript = {
        "schema_version": 1,
        "id": transcript_id,
        "sample_id": sample_id,
        "subject": subject,
        "scenario": f"first real-model baseline over {sample_id}",
        "provenance": "model",
        # Stamped from the record that was just written, so the transcript can
        # never name a capture that does not exist.
        "capture_id": record.capture_id,
        "investigation": payload,
    }
    path = freeze_transcript(transcripts_dir, transcript)
    return CapturedFixture(
        sample_id=sample_id,
        subject=subject,
        transcript_path=path,
        capture=record,
        failure=investigation.failure,
    )


def capture_all(
    subjects: dict[str, str],
    provider: Any,
    session_for: SessionFactory,
    run_id: str,
    captured_at: str,
    transcripts_dir: Path = TRANSCRIPTS_DIR,
    captures_dir: Path = CAPTURES_DIR,
) -> tuple[CapturedFixture, ...]:
    """Every fixture, once each, in a fixed order.

    There is deliberately no fixture argument. A subset parameter is how a
    baseline becomes a selection, and how a poor result becomes a rerun of only
    the fixtures that disappointed.
    """
    expected = dataset_samples()
    if tuple(sorted(subjects)) != expected:
        raise BaselinePreparationError(
            f"the baseline covers exactly {len(expected)} fixtures; got {sorted(subjects)}"
        )
    return tuple(
        _captured(
            sample_id,
            subjects[sample_id],
            provider,
            session_for,
            run_id,
            captured_at,
            transcripts_dir,
            captures_dir,
        )
        for sample_id in expected
    )


def _captured(
    sample_id: str,
    subject: str,
    provider: Any,
    session_for: SessionFactory,
    run_id: str,
    captured_at: str,
    transcripts_dir: Path,
    captures_dir: Path,
) -> CapturedFixture:
    with session_for(sample_id) as session:
        return capture_one(
            sample_id=sample_id,
            subject=subject,
            context=ToolContext(session=session),
            provider=provider,
            run_id=run_id,
            captured_at=captured_at,
            transcripts_dir=transcripts_dir,
            captures_dir=captures_dir,
        )


@contextmanager
def ghidra_sessions(sample_id: str) -> Iterator[Any]:
    """The production session factory. Imported lazily, like every Ghidra path.

    The stripped binary is the only artifact opened. `firmware.symbols`,
    `behavior.dylib` and the ground truth beside it are not read here and must
    not be: what the model is shown is what a stripped binary yields.
    """
    from ecu_recovery.analysis.ghidra import GhidraEngine

    firmware = SAMPLES_ROOT / sample_id / "firmware.stripped"
    if not firmware.is_file():
        raise BaselinePreparationError(f"{sample_id}: no stripped firmware at {firmware}")
    with GhidraEngine().analyze_binary(firmware) as session:
        yield session
