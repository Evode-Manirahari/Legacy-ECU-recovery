"""Load, score, and gate a directory of frozen transcripts."""

from __future__ import annotations

from pathlib import Path

from .adjudication import load_adjudications
from .gate import check_gate
from .models import AgentEvaluationRun, Provenance, TranscriptScore
from .scoring import aggregate, expected_roles, score_transcript, verify_detection
from .transcripts import load_transcripts


def evaluate(
    directory: Path,
    samples_root: Path | None = None,
    adjudications_dir: Path | None = None,
) -> AgentEvaluationRun:
    """Score every transcript in `directory` against its sample's ground truth.

    Provenance is derived rather than asserted: a run counts as a real-model
    baseline only when *every* transcript in it came from a provider. One
    authored transcript in the set is enough to make the whole run
    machinery-verification, because a mixed set would let scripted replies
    quietly inflate a number presented as a model's.
    """
    transcripts = load_transcripts(directory)
    if adjudications_dir is None:
        adjudications_dir = directory.parent / "adjudications"
    adjudications = load_adjudications(adjudications_dir)
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

    detection_mismatches = tuple(
        mismatch
        for transcript, score in zip(transcripts, scores, strict=True)
        for mismatch in verify_detection(transcript, score)
    )
    metrics = aggregate(transcripts, tuple(scores), adjudications)
    kinds = {transcript.provenance for transcript in transcripts}
    real_model = kinds == {"model"}
    return AgentEvaluationRun(
        provenance=Provenance(
            kind="model" if real_model else "authored",
            detail=(
                "every transcript came from a real provider"
                if real_model
                else "scripted replies over real tool output; no model was called"
            ),
        ),
        scores=tuple(scores),
        metrics=metrics,
        gate=check_gate(metrics),
        detection_mismatches=detection_mismatches,
        adversarial=any(transcript.expects for transcript in transcripts),
        adjudicators=tuple(sorted({item.adjudicator for item in adjudications.values()})),
    )
