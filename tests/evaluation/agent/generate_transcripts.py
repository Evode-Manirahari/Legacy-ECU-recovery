"""Produce the frozen transcript fixtures.

    uv run python tests/evaluation/agent/generate_transcripts.py

Run on demand, not during the suite. It needs Ghidra, because the *facts* in
these transcripts are real: the agent runs against the real synthetic corpus
through the real tool layer, and only the model's reply is scripted.

That distinction is what the fixtures are for. A hand-written transcript would
let the scorer agree with a shape nobody produced; these exercise the actual
gathering, citation-checking and demotion path, so a metric that passes here is
detecting something the agent can really emit.

The scenarios are chosen to make each metric fail if it were wrong: a clean
transcript alone cannot show that a detector detects anything.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ecu_recovery.agent import gather_facts, investigate  # noqa: E402
from ecu_recovery.agent.provider import ModelRequest, ModelResponse  # noqa: E402
from ecu_recovery.analysis.ghidra import GhidraEngine  # noqa: E402
from ecu_recovery.tools import ToolContext  # noqa: E402

#: The complete detector vector each fixture expects. Complete on purpose:
#: comparing only the fields a fixture chose to mention would catch a missed
#: defect and never an invented one, and "no false positives" is half of what a
#: detector has to prove.
#:
#: The defect-relevant entries are reasoned, not copied. 04 carries a factual
#: claim with no citation, so it must score one unsupported claim even though
#: AGENT-001 demoted it - the agent catching an overreach is not the model
#: declining to make one. 07 is well-cited and wrong, so it scores zero
#: unsupported: its wrongness is semantic and stays unmeasured.
EXPECTS: dict[str, dict[str, object]] = {
    "01-supported": {
        "parsed": True,
        "claims": 2,
        "factual_claims": 2,
        "raw_factual_claims": 2,
        "citations": 3,
        "valid_citations": 3,
        "fabricated_citations": 0,
        "unsupported_factual_claims": 0,
        "demotions": 0,
    },
    "02-fabricated-citation": {
        "parsed": True,
        "claims": 1,
        "factual_claims": 0,
        "raw_factual_claims": 1,
        "citations": 1,
        "valid_citations": 0,
        "fabricated_citations": 1,
        "unsupported_factual_claims": 1,
        "demotions": 1,
    },
    "03-mixed-citations": {
        "parsed": True,
        "claims": 1,
        "factual_claims": 0,
        "raw_factual_claims": 1,
        "citations": 2,
        "valid_citations": 1,
        "fabricated_citations": 1,
        "unsupported_factual_claims": 1,
        "demotions": 1,
    },
    "04-unsupported-assertion": {
        "parsed": True,
        "claims": 1,
        "factual_claims": 0,
        "raw_factual_claims": 1,
        "citations": 0,
        "valid_citations": 0,
        "fabricated_citations": 0,
        "unsupported_factual_claims": 1,
        "demotions": 1,
    },
    "05-honest-unknown": {
        "parsed": True,
        "claims": 1,
        "factual_claims": 0,
        "raw_factual_claims": 0,
        "citations": 0,
        "valid_citations": 0,
        "fabricated_citations": 0,
        "unsupported_factual_claims": 0,
        "demotions": 0,
    },
    "06-malformed-reply": {
        "parsed": False,
        "claims": 0,
        "factual_claims": 0,
        "raw_factual_claims": 0,
        "citations": 0,
        "valid_citations": 0,
        "fabricated_citations": 0,
        "unsupported_factual_claims": 0,
        "demotions": 0,
    },
    "07-wrong-classification": {
        "parsed": True,
        "claims": 1,
        "factual_claims": 1,
        "raw_factual_claims": 1,
        "citations": 1,
        "valid_citations": 1,
        "fabricated_citations": 0,
        "unsupported_factual_claims": 0,
        "demotions": 0,
    },
    "08-confidence-extremes": {
        "parsed": True,
        "claims": 2,
        "factual_claims": 2,
        "raw_factual_claims": 2,
        "citations": 2,
        "valid_citations": 2,
        "fabricated_citations": 0,
        "unsupported_factual_claims": 0,
        "demotions": 0,
    },
}

#: Authored reviews. Two reviewers per transcript, because the metrics they feed
#: require two, and a fixture set that could not express a second opinion would
#: make the quorum rule untestable.
#:
#: They are labelled `authored`, which is what keeps them out of the gate: a
#: label written to check the scorer is not a reviewer's verdict, however many
#: of them there are. 03 carries a deliberate disagreement so the reconciliation
#: policy has something to refuse to resolve.
#:
#: `classification_correct` is one verdict per review for the whole subject.
#: 08 provokes two claims and still gets one classification vote, which is the
#: point: the question is whether the function was identified.
REVIEWS: dict[str, list[dict[str, object]]] = {
    "01-supported": [
        {
            "reviewer": "authored-a",
            "classification_correct": True,
            "judgements": [
                {"claim_index": 0, "semantically_supported": True, "critical": False},
                {"claim_index": 1, "semantically_supported": True, "critical": False},
            ],
        },
        {
            "reviewer": "authored-b",
            "classification_correct": True,
            "judgements": [
                {"claim_index": 0, "semantically_supported": True, "critical": False},
                {"claim_index": 1, "semantically_supported": True, "critical": False},
            ],
        },
    ],
    "03-mixed-citations": [
        {
            "reviewer": "authored-a",
            "classification_correct": False,
            "judgements": [{"claim_index": 0, "semantically_supported": False, "critical": True}],
        },
        {
            "reviewer": "authored-b",
            "classification_correct": True,
            "judgements": [{"claim_index": 0, "semantically_supported": True, "critical": True}],
        },
    ],
    "04-unsupported-assertion": [
        {
            "reviewer": "authored-a",
            "classification_correct": False,
            "judgements": [{"claim_index": 0, "semantically_supported": False, "critical": True}],
        },
        {
            "reviewer": "authored-b",
            "classification_correct": False,
            "judgements": [{"claim_index": 0, "semantically_supported": False, "critical": True}],
        },
    ],
    "05-honest-unknown": [
        {
            "reviewer": "authored-a",
            "classification_correct": False,
            "judgements": [{"claim_index": 0, "semantically_supported": True, "critical": False}],
        },
        {
            "reviewer": "authored-b",
            "classification_correct": False,
            "judgements": [{"claim_index": 0, "semantically_supported": True, "critical": False}],
        },
    ],
    "07-wrong-classification": [
        {
            "reviewer": "authored-a",
            "classification_correct": False,
            "judgements": [{"claim_index": 0, "semantically_supported": False, "critical": True}],
        },
        {
            "reviewer": "authored-b",
            "classification_correct": False,
            "judgements": [{"claim_index": 0, "semantically_supported": False, "critical": True}],
        },
    ],
    "08-confidence-extremes": [
        {
            "reviewer": "authored-a",
            "classification_correct": True,
            "judgements": [
                {"claim_index": 0, "semantically_supported": True, "critical": False},
                {"claim_index": 1, "semantically_supported": False, "critical": False},
            ],
        },
        {
            "reviewer": "authored-b",
            "classification_correct": True,
            "judgements": [
                {"claim_index": 0, "semantically_supported": True, "critical": False},
                {"claim_index": 1, "semantically_supported": False, "critical": False},
            ],
        },
    ],
}

SAMPLE = "multi_function_pipeline_v1"
FIRMWARE = ROOT / "samples" / "synthetic" / "binaries" / SAMPLE / "firmware.stripped"
OUT = Path(__file__).resolve().parent / "transcripts"
ADJ = Path(__file__).resolve().parent / "adjudications"


class Scripted:
    """A provider that returns a fixed reply. No model, no network."""

    def __init__(self, reply: str, name: str = "scripted") -> None:
        self.reply = reply
        self.name = name

    def complete(self, request: ModelRequest) -> ModelResponse:
        del request
        return ModelResponse(text=self.reply, provider=self.name, model="authored")


def claims(*items: dict[str, object]) -> str:
    return json.dumps({"claims": list(items)})


def symbols() -> dict[int, str]:
    out = subprocess.run(
        ["nm", "-n", str(FIRMWARE.with_name("firmware.symbols"))],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {
        int(parts[0], 16): parts[2].removeprefix("_")
        for parts in (line.split() for line in out.splitlines())
        if len(parts) == 3 and parts[1].lower() == "t"
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ADJ.mkdir(parents=True, exist_ok=True)
    for stale in [*OUT.glob("*.json"), *ADJ.glob("*.json")]:
        stale.unlink()

    names = symbols()
    engine = GhidraEngine()
    written = 0
    with engine.analyze_binary(FIRMWARE) as session:
        context = ToolContext(session=session)
        functions = session.list_functions(limit=100)
        by_name = {names[item.start_address]: item.id for item in functions}
        subject = by_name["control_output"]
        other = by_name["apply_gain"]
        sheet = gather_facts(context, subject)
        real = [fact.id for fact in sheet.facts]

        # Each scenario targets one thing a metric must notice. A suite of clean
        # transcripts would prove only that nothing objected.
        scenarios: list[tuple[str, str, str, str, str]] = [
            (
                "01-supported",
                subject,
                "control_output",
                "every factual claim carries citations that all resolve",
                claims(
                    {
                        "statement": "runs normalization then gain then clamping as a pipeline",
                        "support": "observed",
                        "confidence": 0.9,
                        "citations": [real[3], real[4]],
                    },
                    {
                        "statement": "calls three helper routines in sequence",
                        "support": "inferred",
                        "confidence": 0.7,
                        "citations": [real[4]],
                    },
                ),
            ),
            (
                "02-fabricated-citation",
                subject,
                "control_output",
                "a claim citing a fact that was never gathered",
                claims(
                    {
                        "statement": "writes directly to an injector register",
                        "support": "observed",
                        "confidence": 0.95,
                        "citations": ["F900"],
                    }
                ),
            ),
            (
                "03-mixed-citations",
                subject,
                "control_output",
                "one resolving citation beside one fabricated citation",
                claims(
                    {
                        "statement": "clamps its output to a calibration ceiling",
                        "support": "observed",
                        "confidence": 0.88,
                        "citations": [real[0], "F901"],
                    }
                ),
            ),
            (
                "04-unsupported-assertion",
                subject,
                "control_output",
                "a factual claim carrying no citation at all",
                claims(
                    {
                        "statement": "is the engine speed governor",
                        "support": "observed",
                        "confidence": 0.8,
                        "citations": [],
                    }
                ),
            ),
            (
                "05-honest-unknown",
                other,
                "apply_gain",
                "the agent declining to answer, correctly",
                claims(
                    {
                        "statement": "the scaling factor is not determinable from these facts",
                        "support": "unknown",
                        "confidence": 0.0,
                    }
                ),
            ),
            (
                "06-malformed-reply",
                subject,
                "control_output",
                "a reply that is not usable JSON",
                "I think this function probably handles fuel injection timing.",
            ),
            (
                "07-wrong-classification",
                other,
                "apply_gain",
                "well-cited claims describing the wrong role",
                claims(
                    {
                        "statement": "parses a diagnostic message header",
                        "support": "observed",
                        "confidence": 0.85,
                        "citations": [real[1]],
                    }
                ),
            ),
            (
                "08-confidence-extremes",
                subject,
                "control_output",
                "maximum and minimum stated confidence side by side",
                claims(
                    {
                        "statement": "invokes at least one helper",
                        "support": "observed",
                        "confidence": 1.0,
                        "citations": [real[4]],
                    },
                    {
                        "statement": "might implement a lookup table",
                        "support": "inferred",
                        "confidence": 0.05,
                        "citations": [real[2]],
                    },
                ),
            ),
        ]

        for transcript_id, target, role, scenario, reply in scenarios:
            result = investigate(context, target, Scripted(reply))
            payload = result.as_dict()
            # The role is recorded on the transcript so scoring can reach the
            # answer key without the agent ever having seen it.
            payload["ground_truth_role"] = role
            (OUT / f"{transcript_id}.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": transcript_id,
                        "sample_id": SAMPLE,
                        "subject": target,
                        "scenario": scenario,
                        "provenance": "authored",
                        "expects": EXPECTS[transcript_id],
                        "investigation": payload,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            written += 1
            for review in REVIEWS.get(transcript_id, []):
                (ADJ / f"{transcript_id}.{review['reviewer']}.json").write_text(
                    json.dumps(
                        {
                            "transcript_id": transcript_id,
                            "reviewer": review["reviewer"],
                            "kind": "authored",
                            "classification_correct": review["classification_correct"],
                            "judgements": review["judgements"],
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
    print(f"wrote {written} transcripts to {OUT}")
    print(f"wrote {sum(len(v) for v in REVIEWS.values())} reviews to {ADJ}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
