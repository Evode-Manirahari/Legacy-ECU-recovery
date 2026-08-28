"""Load, score, and gate a directory of frozen transcripts."""

from __future__ import annotations

from pathlib import Path

from .adjudication import load_panel
from .captures import verify_linkage
from .gate import check_gate
from .models import AgentEvaluationRun, Provenance, TranscriptScore
from .scoring import aggregate, expected_roles, score_transcript, verify_detection
from .transcripts import Transcript, load_transcripts

#: Unchanged, and load-bearing. This is what the recorded score of the authored
#: corpus says, and that artifact is the control for the provenance repair: if
#: the sentence moved, the repair changed what the evaluator reports about a
#: corpus nobody touched.
AUTHORED_DETAIL = "scripted replies over real tool output; no model was called"


def _linkage_of(transcripts: tuple[Transcript, ...], captures_dir: Path) -> dict[str, str]:
    """Check every claim of model provenance once, and keep why each failed.

    Computed in one place because two questions now depend on it. Provenance
    asks whether the corpus is a real baseline; detector scope asks whether a
    given transcript is a captured sample or a fixture. Both must answer from
    the same verified linkage, or a transcript could be a capture for one
    purpose and a fixture for the other.
    """
    return {
        transcript.id: verify_linkage(transcript, captures_dir)
        for transcript in transcripts
        if transcript.claims_model
    }


def _is_verified_capture(transcript: Transcript, linkage: dict[str, str]) -> bool:
    """Whether this transcript is a real sample rather than a fixture.

    Derived from the capture record, never from `transcript.provenance`. A
    transcript that could exempt itself from detector verification by calling
    itself a capture would hand back, in a new place, what the linkage check
    exists to prevent: a claim standing in for evidence of the same claim.
    """
    return transcript.claims_model and linkage.get(transcript.id, "unchecked") == ""


def _provenance_of(transcripts: tuple[Transcript, ...], linkage: dict[str, str]) -> Provenance:
    """Decide what this corpus is, from the capture records rather than the labels."""
    claiming = [transcript for transcript in transcripts if transcript.claims_model]
    if not claiming:
        return Provenance(kind="authored", detail=AUTHORED_DETAIL)

    reasons = tuple(reason for reason in (linkage[item.id] for item in claiming) if reason)
    if reasons:
        return Provenance(
            kind="authored",
            detail=(
                "a claim of model provenance is not backed by a verified capture record: "
                + "; ".join(reasons)
            ),
        )
    if len(claiming) != len(transcripts):
        return Provenance(
            kind="authored",
            detail=(
                f"mixed corpus: {len(claiming)} of {len(transcripts)} transcripts claim model "
                "provenance, and a set that is partly scripted is not a baseline of anything"
            ),
        )
    return Provenance(
        kind="model",
        detail=(
            f"every transcript came from a real provider, each linked to a verified capture "
            f"record ({len(claiming)} of {len(transcripts)}). The records are verified as "
            "artifacts - unedited, and written for the transcripts that reference them - which "
            "is not proof that a provider made the call. The provider-issued response ids are "
            "what a human can check against the provider's own records."
        ),
    )


def evaluate(
    directory: Path,
    samples_root: Path | None = None,
    adjudications_dir: Path | None = None,
    captures_dir: Path | None = None,
) -> AgentEvaluationRun:
    """Score every transcript in `directory` against its sample's ground truth.

    Provenance is derived rather than asserted, and "derived" now means checked
    against an artifact. A run counts as a real-model baseline only when every
    transcript in it claims to be one *and* each claim is backed by a capture
    record that exists, matches its own contents, was written for that
    transcript, and agrees with it field for field.

    Reading the claim itself was the whole defect. A hand-written transcript
    saying `"provenance": "model"` was reported as a real-model baseline, which
    satisfied two of `GATE-AGENT-MVP`'s invariants on the strength of a word
    somebody typed. The word is now a claim the evaluator checks.

    One transcript that fails makes the whole run authored, exactly as one
    authored transcript already did: a mixed set would let unbacked replies
    inflate a number presented as a model's.

    The check can only refuse. Nothing here promotes a transcript that did not
    arrive claiming model provenance, so no existing corpus scores differently.
    """
    transcripts = load_transcripts(directory)
    if adjudications_dir is None:
        adjudications_dir = directory.parent / "adjudications"
    if captures_dir is None:
        captures_dir = directory.parent / "captures"
    panel = load_panel(adjudications_dir)
    roles_by_sample: dict[str, dict[str, str]] = {}
    scores: list[TranscriptScore] = []
    for transcript in transcripts:
        if transcript.sample_id not in roles_by_sample:
            roles_by_sample[transcript.sample_id] = expected_roles(
                transcript.sample_id, samples_root
            )
        roles = roles_by_sample[transcript.sample_id]
        role_name = str(transcript.investigation.get("ground_truth_role", "")) or None
        role_text = roles.get(role_name) if role_name else None
        scores.append(score_transcript(transcript, role_name, role_text))

    # Detector verification applies to fixtures, not to captured samples. A
    # fixture declares what it plants so the scorer can be held to finding
    # exactly that; nothing is planted in a real call, so a captured transcript
    # has nothing to declare and reporting its silence as a mismatch called
    # genuine samples defective fixtures. Scope is what changed here - the
    # check itself is untouched, and an authored fixture with no expectations
    # is still a fixture bug.
    linkage = _linkage_of(transcripts, captures_dir)
    in_scope = tuple(
        (transcript, score)
        for transcript, score in zip(transcripts, scores, strict=True)
        if not _is_verified_capture(transcript, linkage)
    )
    detection_mismatches = tuple(
        mismatch
        for transcript, score in in_scope
        for mismatch in verify_detection(transcript, score)
    )
    metrics = aggregate(transcripts, tuple(scores), panel)
    return AgentEvaluationRun(
        provenance=_provenance_of(transcripts, linkage),
        scores=tuple(scores),
        metrics=metrics,
        gate=check_gate(metrics),
        detection_mismatches=detection_mismatches,
        detection_in_scope=len(in_scope),
        adversarial=any(transcript.expects for transcript in transcripts),
        adjudicators=panel.kinds,
    )
