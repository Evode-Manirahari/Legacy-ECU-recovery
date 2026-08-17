"""Human-readable, evidence-preserving report generation."""

from __future__ import annotations

import json
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
                f"- Status: **{row['certainty']}**",
                f"- Confidence: {row['confidence']:.0%}",
                f"- Uncertainty: {row['uncertainty'] or 'None recorded'}",
                "- Evidence:",
            ]
        )
        lines.extend(f"  - {item}" for item in evidence)
        if not evidence:
            lines.append("  - No evidence recorded")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(store: InvestigationStore, analysis_id: int, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(store, analysis_id), encoding="utf-8")
    return path
