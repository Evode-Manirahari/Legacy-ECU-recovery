"""Human-readable, evidence-preserving report generation.

The report has to say what the evidence model actually knows. Two axes are kept
apart because the model keeps them apart: `Certainty` is what kind of statement
a claim is - mechanically known, inferred, or admittedly unknown - and
`HypothesisStatus` is what testing has done to it. A claim can be inferred and
supported at the same time, and collapsing the two loses the difference between
a fact and a well-tested guess.

An earlier version rendered `certainty` under the label "Status" and never
showed `HypothesisStatus` at all, which meant a REJECTED belief read exactly
like an UNTESTED one. INTEGRATION-STATIC-001 found that; this module is the
repair.

Belief history is rendered for any hypothesis that has moved, because "the
system changed its mind, and here is why" is the thing the evidence model exists
to record. Only stored fields are shown - no interpretation is invented here.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .store import InvestigationStore


def render_markdown(store: InvestigationStore, analysis_id: int) -> str:
    analysis, functions, hypotheses = store.report_data(analysis_id)
    profile = json.loads(analysis["profile_json"])
    processor = analysis["processor"] or "Unknown (manual selection required)"
    byte_order = analysis["byte_order"] or "Unknown"
    lines = [
        f"# Firmware analysis: {analysis['filename']}",
        "",
        "> Static investigation artifact. Do not treat this report as authorization "
        "or guidance to flash hardware.",
        "",
        "## Intake facts",
        "",
        f"- Size: {analysis['size']} bytes",
        f"- SHA-256: `{analysis['sha256']}`",
        f"- SHA-1: `{analysis['sha1']}`",
        f"- MD5: `{analysis['md5']}`",
        f"- Shannon entropy: {analysis['entropy']:.4f} bits/byte",
        f"- Processor: {processor}",
        f"- Byte order: {byte_order}",
        f"- Fill-byte counts: {profile['fill_bytes'] or 'none'}",
        f"- Repeated 256-byte blocks reported: {len(profile['repeated_regions'])}",
        "",
        "## Functions",
        "",
    ]
    if functions:
        lines.extend(
            f"- `0x{row['address']:X}` — {row['name']}"
            + (f" ({row['size']} bytes)" if row["size"] is not None else "")
            for row in functions
        )
    else:
        lines.append("No function records imported yet.")

    lines.extend(["", "## Hypotheses and evidence", ""])
    if not hypotheses:
        lines.append("No hypotheses recorded yet. Unknowns remain explicitly unknown.")
    for row in hypotheses:
        evidence = json.loads(row["evidence_json"])
        lines.extend(
            [
                f"### {row['subject']}",
                "",
                f"- Claim: {row['claim']}",
                # Two separate lines for two separate ideas. See the module
                # docstring: labelling certainty as "Status" is what made a
                # rejected belief indistinguishable from an untested one.
                f"- Certainty: **{row['certainty']}**",
                f"- Hypothesis status: **{row['status']}**",
                f"- Confidence: {row['confidence']:.0%}",
                f"- Uncertainty: {row['uncertainty'] or 'None recorded'}",
                "- Evidence:",
            ]
        )
        lines.extend(f"  - {item}" for item in evidence)
        if not evidence:
            lines.append("  - No evidence recorded")
        lines.append("")
        lines.extend(_belief_history(store, analysis_id, row))
    return "\n".join(lines).rstrip() + "\n"


def _belief_history(store: InvestigationStore, analysis_id: int, current: sqlite3.Row) -> list[str]:
    """Render how a belief reached its current state, if it moved at all.

    A single-revision belief has no history worth a table; showing one would be
    noise on every report. A belief that moved gets the whole chain, because the
    reason it moved is exactly what a reader needs in order to disagree with it.

    The current revision is marked rather than merely being last. Nothing here
    may read as a second, simultaneously-held belief.
    """
    history = store.hypothesis_history(analysis_id, str(current["hypothesis_key"]))
    if len(history) < 2:
        return []
    lines = [
        f"Belief history — current revision is {int(current['revision'])}:",
        "",
        "| Revision | Hypothesis status | Confidence | Recorded reason |",
        "|---:|---|---:|---|",
    ]
    for revision in history:
        marker = " (current)" if revision.revision == int(current["revision"]) else ""
        lines.append(
            f"| {revision.revision}{marker} | {revision.status.value} | "
            f"{revision.confidence:.0%} | {revision.change_reason} |"
        )
    lines.append("")
    return lines


def write_markdown(store: InvestigationStore, analysis_id: int, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(store, analysis_id), encoding="utf-8")
    return path
