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

import importlib
import json
import os
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecu_recovery.agent import InvestigationBudget, investigate
from ecu_recovery.agent.models import canonical_digest
from ecu_recovery.evaluation.agent.captures import CaptureRecord, record_for, write_capture
from ecu_recovery.providers.openai import (
    API_KEY_VARIABLE,
    MODEL_VARIABLE,
    OpenAIProvider,
    provider_from_environment,
)
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

#: The transport the live baseline needs present on this machine, and the symbol
#: the adapter actually reaches for. Named here rather than inlined so the check
#: and the thing being checked cannot drift apart silently.
TRANSPORT_MODULE = "openai"
TRANSPORT_SYMBOL = "OpenAI"

#: How to install it. Put in the refusal, because a refusal that does not say
#: what to do next is a puzzle rather than a guard.
TRANSPORT_INSTALL = "uv sync --extra openai --frozen"

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


def require_provider_configuration(environ: Mapping[str, str] | None = None) -> str:
    """Refuse to start a live capture that is not configured to make one.

    The failure this prevents is quiet rather than loud. `investigate` records
    an unreachable provider as an *outcome*, so an unset key does not stop a
    run - it produces eight transcripts of failures, each labelled
    `provenance: model`, each backed by a capture record the evaluator verifies,
    and the whole thing reads to the evaluator as a real baseline against a
    provider having a very bad day. Configuration is therefore checked before
    the first call rather than discovered during it.

    Only the model identifier is returned, and only the *names* of missing
    variables are ever put in the message. The key is checked for presence and
    then dropped: this function must never be the reason a credential reaches a
    log, an exception, or a frozen artifact.
    """
    env = os.environ if environ is None else environ
    missing = [
        name for name in (API_KEY_VARIABLE, MODEL_VARIABLE) if not str(env.get(name, "")).strip()
    ]
    if missing:
        raise BaselinePreparationError(
            f"the live baseline is not configured: {', '.join(missing)} "
            f"{'are' if len(missing) > 1 else 'is'} unset or empty. "
            "No call was made and nothing was written."
        )
    return str(env[MODEL_VARIABLE]).strip()


def require_transport(import_module: Callable[[str], Any] | None = None) -> str:
    """Prove the transport exists on this machine, before anything is spent.

    Configuration being *present* is not the transport being *available*, and
    the gap between those two is not academic. With both variables set and the
    extra absent, `_resolve_client` raises `ModelUnavailableError` from inside
    the call; `investigate` records an unreachable provider as an **outcome**
    rather than an error; and the run completes with eight transcripts labelled
    `provenance: model`, eight capture records the evaluator verifies, and
    `is_real_model=True` - without one request leaving the machine. A complete
    baseline of nothing, indistinguishable from a real one taken during an
    outage, and frozen at capture so that finding it afterwards costs a second
    round of real calls.

    The import is attempted rather than merely resolved. `find_spec` would
    answer "is it on the path", and the question worth asking is the one the
    adapter will ask a moment later: does `from openai import OpenAI` work. A
    findable-but-broken install passes the first and fails the second, which
    would put the whole defect back exactly where it was.

    **This is a local check and must stay one.** No client is constructed, no
    credential is read, and nothing is sent. Whether the provider answers, and
    what it says, is the experiment - not its precondition. Once capture begins
    a provider or network failure is an outcome to be frozen and reported, never
    a reason to retry, adapt, or probe first.
    """
    load = importlib.import_module if import_module is None else import_module
    try:
        module = load(TRANSPORT_MODULE)
    except Exception as error:  # noqa: BLE001 - any import failure is unreadiness
        # The exception's *type* only. Its message is arbitrary text from
        # somewhere this module does not control, and this string is printed;
        # `from error` keeps the full detail on the traceback for a human
        # without putting it in a line something might log.
        raise BaselinePreparationError(
            f"the {TRANSPORT_MODULE} transport is not importable here "
            f"({type(error).__name__}). Run `{TRANSPORT_INSTALL}` first. "
            "No call was made and nothing was written."
        ) from error
    if not hasattr(module, TRANSPORT_SYMBOL):
        raise BaselinePreparationError(
            f"{TRANSPORT_MODULE} is importable but exposes no {TRANSPORT_SYMBOL}; "
            f"the installed package is not the transport this expects. "
            f"Run `{TRANSPORT_INSTALL}`. No call was made and nothing was written."
        )
    return str(getattr(module, "__version__", "") or "unknown")


def preflight_destinations(transcripts_dir: Path, captures_dir: Path) -> None:
    """Refuse, before the first call, if a baseline already stands here.

    `freeze_transcript` also refuses to overwrite, but it refuses one fixture at
    a time and only *after* that fixture's call has been paid for and its
    capture record written. Rerunning a completed baseline therefore cost one
    live call and left one orphan capture behind before anything objected.

    Any prior state aborts the whole run: a completed baseline, a partial one
    from an interrupted attempt, or a single stray record. What to do with what
    is already there is a decision for a person, and having to make it by hand
    is the point - an automatic resume is how half of one run and half of
    another become a single "baseline".
    """
    standing = sorted(
        path.name
        for directory in (transcripts_dir, captures_dir)
        if directory.is_dir()
        for path in directory.glob("*.json")
    )
    if standing:
        raise BaselinePreparationError(
            f"a baseline already stands here: {len(standing)} file(s) under "
            f"{transcripts_dir.name}/ and {captures_dir.name}/, first {standing[0]}. "
            "No call was made and nothing was written. Move or delete the existing "
            "capture deliberately before running again."
        )


def check_subjects_are_frozen(
    subjects: dict[str, str],
    manifest_path: Path = SUBJECT_MANIFEST,
    expected_manifest_id: str = SUBJECT_MANIFEST_ID,
) -> None:
    """The subjects about to be captured must be the ones that were frozen.

    Coverage was already checked - eight fixtures, exactly the dataset's. That
    says nothing about *where in each binary* the model is pointed, and an
    address is the easier thing to change: it is one character in a mapping, it
    breaks no test of coverage, and the resulting run looks in every other
    respect like the baseline that was agreed.

    So the mapping is compared against `load_subject_manifest` element by
    element, before the first call. Passing a mapping in at all is a
    convenience for the tests; the frozen manifest is the authority, and a
    mapping that disagrees with it by one address does not capture.
    """
    frozen = load_subject_manifest(manifest_path, expected_manifest_id)
    differing = sorted(name for name, subject in frozen.items() if subjects.get(name) != subject)
    if differing:
        raise BaselinePreparationError(
            f"the subjects handed to the capture are not the frozen ones: {differing} "
            f"differ from {manifest_path.name}. No call was made and nothing was written."
        )


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
    manifest_path: Path = SUBJECT_MANIFEST,
    expected_manifest_id: str = SUBJECT_MANIFEST_ID,
    environ: Mapping[str, str] | None = None,
    import_module: Callable[[str], Any] | None = None,
) -> tuple[CapturedFixture, ...]:
    """Every fixture, once each, in a fixed order.

    There is deliberately no fixture argument. A subset parameter is how a
    baseline becomes a selection, and how a poor result becomes a rerun of only
    the fixtures that disappointed.

    Three things are settled before the first call, in this order, because each
    one is a way a run could otherwise spend money on the wrong measurement:
    coverage is exactly the dataset's eight, the subjects are exactly the frozen
    ones, and no baseline already stands in the destination. A live provider is
    additionally required to be configured and to have its transport importable
    here. All of them refuse with nothing called and nothing written.
    """
    expected = dataset_samples()
    if tuple(sorted(subjects)) != expected:
        raise BaselinePreparationError(
            f"the baseline covers exactly {len(expected)} fixtures; got {sorted(subjects)}"
        )
    check_subjects_are_frozen(subjects, manifest_path, expected_manifest_id)
    if isinstance(provider, OpenAIProvider):
        # A live transport resolves its credential and imports its SDK inside
        # the call, and both failures come back through the declared boundary as
        # ordinary failed investigations. Checking here as well as in
        # `run_live_baseline` means the guarantee belongs to the capture rather
        # than to the entry point somebody happened to use. Neither check runs
        # for a double: a scripted provider needs no credential and no SDK.
        require_provider_configuration(environ)
        require_transport(import_module)
    preflight_destinations(transcripts_dir, captures_dir)
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


def run_live_baseline(
    run_id: str,
    captured_at: str,
    transcripts_dir: Path = TRANSCRIPTS_DIR,
    captures_dir: Path = CAPTURES_DIR,
    session_for: SessionFactory | None = None,
    environ: Mapping[str, str] | None = None,
    import_module: Callable[[str], Any] | None = None,
) -> tuple[CapturedFixture, ...]:
    """The one path that spends money, and the five refusals in front of it.

    Every check happens before a provider is even built, so a run that is going
    to be refused is refused having called nothing and written nothing:

    1. the credential and the model identifier are configured;
    2. the transport is importable on this machine;
    3. the subject manifest still has the identity that was frozen;
    4. the subjects are exactly those subjects;
    5. no transcript or capture already stands in the destination.

    Checks 1 and 2 are separate because they fail for opposite reasons and only
    one of them looks like configuration. Both variables can be set correctly on
    a machine where the SDK was never installed.

    The model identifier comes from the environment and is never defaulted here
    - the adapter has no default either, so nothing in this project names a
    snapshot the API has not been seen to report.

    Run it under the frozen environment, with the extra:

        uv run --extra openai --frozen python -c "
        import sys; sys.path.insert(0, 'tests/agent_baseline')
        from capture_harness import run_live_baseline
        run_live_baseline(run_id='...', captured_at='...')"

    `--frozen` every time, and `git diff --exit-code uv.lock` before committing.
    A bare `uv run` re-resolved and bumped openai 3.3.1 -> 3.5.0 once already,
    and this is the run whose whole purpose is a frozen artifact.

    This function is deliberately not called by anything. `BASELINE-AGENT-001`
    is a human/spend gate: somebody exports two variables and runs it once.
    """
    model = require_provider_configuration(environ)
    require_transport(import_module)
    subjects = load_subject_manifest()
    preflight_destinations(transcripts_dir, captures_dir)
    return capture_all(
        subjects=subjects,
        # The identifier that was just checked is the identifier that is used,
        # rather than read a second time from somewhere that could disagree.
        provider=provider_from_environment(model=model),
        session_for=ghidra_sessions if session_for is None else session_for,
        run_id=run_id,
        captured_at=captured_at,
        transcripts_dir=transcripts_dir,
        captures_dir=captures_dir,
        environ=environ,
        import_module=import_module,
    )
