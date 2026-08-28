"""The frozen subject manifest, locked.

`BASELINE-AGENT-001` spends money and freezes what it gets. What it investigates
is therefore decided here, once, and pinned — so that a change to any of it is a
visible diff in this file rather than a different experiment wearing the same
name.

The identity covers content, not bytes: reindenting the manifest or reordering
its keys leaves it alone, and changing any subject does not.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capture_harness import (
    SUBJECT_MANIFEST,
    SUBJECT_MANIFEST_ID,
    dataset_samples,
    load_subject_manifest,
    manifest_body,
    manifest_id,
)

#: The frozen mapping, restated. Duplication is the point: this is a tripwire,
#: and a tripwire that reads its value from the thing it guards is not one.
#:
#: Each address is the single function that fixture's `sample_probe` invokes,
#: verified against the unstripped binaries outside the harness before freezing.
FROZEN_SUBJECTS = {
    "bitmask_manipulation_v1": "0x100000ee0",
    "lookup_1d_v1": "0x100000ea0",
    "lookup_2d_v1": "0x100000ec0",
    "multi_function_pipeline_v1": "0x100000f00",
    "rpm_calculation_v1": "0x100000f10",
    "state_machine_v1": "0x100000ef0",
    "temperature_controller_v1": "0x100000f40",
    "timer_counter_v1": "0x100000eb0",
}

FROZEN_ID = "M-dd677b4a5603966052d08feb7de8e7f01d98a6186044ed7cea4fd93ecacd0248"

#: Recorded during experiment-design review outside this repository, and
#: superseded before any model call because its canonical body could not be
#: reconstructed. Named here so that a future reader meeting it in an old note
#: can find out what happened to it rather than assuming a manifest was altered.
SUPERSEDED_ID = "M-c940a1336f8af121ae6ba26e4a422de67bfaf7466b573dc0f88a666d8352515f"


def committed() -> dict[str, Any]:
    payload = json.loads(SUBJECT_MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_the_manifest_identity_is_locked() -> None:
    assert SUBJECT_MANIFEST_ID == FROZEN_ID


def test_the_committed_manifest_reproduces_that_identity() -> None:
    payload = committed()

    assert manifest_id(manifest_body(payload)) == FROZEN_ID
    assert payload["manifest_id"] == FROZEN_ID


def test_the_loader_accepts_the_committed_manifest() -> None:
    assert load_subject_manifest() == FROZEN_SUBJECTS


def test_the_subjects_are_exactly_the_frozen_eight() -> None:
    payload = committed()

    assert payload["subjects"] == FROZEN_SUBJECTS
    assert tuple(sorted(FROZEN_SUBJECTS)) == dataset_samples()
    assert len(FROZEN_SUBJECTS) == 8


def test_the_body_states_the_rule_the_weighting_and_the_exclusions() -> None:
    """The manifest has to explain itself, or the identity pins a bare table."""
    body = manifest_body(committed())

    assert body["schema_version"] == 1
    assert body["selection_rule"] == (
        "subject is the single function invoked by each fixture's sample_probe"
    )
    assert body["weighting"] == "equal: one subject per fixture"
    assert body["exclusions"] == (
        "no function names, semantic roles, expected labels, claims, or answers"
    )


def test_the_body_is_exactly_those_five_fields() -> None:
    """Minimal on purpose. A field nobody decided to freeze is a field that can
    change what the identity means without anyone noticing."""
    assert set(manifest_body(committed())) == {
        "schema_version",
        "selection_rule",
        "weighting",
        "exclusions",
        "subjects",
    }


def test_the_manifest_carries_no_answers() -> None:
    """It names addresses. What the functions do is what is being measured.

    Fixture ids are removed before looking, because two of them contain their
    own subject's name — `lookup_1d_v1` spells `lookup_1d` — and a dataset
    identifier is not a disclosure of anything.
    """
    text = json.dumps(committed())
    for fixture_id in FROZEN_SUBJECTS:
        text = text.replace(fixture_id, "")

    for leaked in (
        "bitmask_status",
        "lookup_1d",
        "lookup_2d",
        "control_output",
        "rpm_from_period",
        "next_state",
        "temperature_fan_on",
        "elapsed_ticks",
    ):
        assert leaked not in text, leaked


def test_the_superseded_identity_is_not_the_frozen_one() -> None:
    """It was replaced, not silently reused, and never verified this manifest."""
    payload = committed()

    assert FROZEN_ID != SUPERSEDED_ID
    assert SUPERSEDED_ID not in json.dumps(payload)
    assert manifest_id(manifest_body(payload)) != SUPERSEDED_ID


def test_the_supersession_is_documented_beside_the_manifest() -> None:
    notes = (SUBJECT_MANIFEST.parent / "README.md").read_text(encoding="utf-8")

    assert SUPERSEDED_ID in notes
    assert "superseded" in notes
    assert "before any model call" in notes


def test_the_identity_survives_reformatting(tmp_path: Path) -> None:
    """Content, not bytes. Proved on the committed manifest itself."""
    payload = committed()
    compact = tmp_path / "compact.json"
    compact.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    assert compact.read_bytes() != SUBJECT_MANIFEST.read_bytes()
    assert load_subject_manifest(compact, FROZEN_ID) == FROZEN_SUBJECTS


def test_moving_one_subject_breaks_the_identity(tmp_path: Path) -> None:
    payload = committed()
    payload["subjects"] = {**FROZEN_SUBJECTS, "state_machine_v1": "0x100000eff"}
    moved = tmp_path / "moved.json"
    moved.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert manifest_id(manifest_body(payload)) != FROZEN_ID


def test_every_subject_is_an_address_and_nothing_else() -> None:
    """Structural, so a name cannot arrive in the value side either."""
    import re

    subjects = committed()["subjects"]
    assert isinstance(subjects, dict)
    for fixture_id, address in subjects.items():
        assert fixture_id in dataset_samples()
        assert re.fullmatch(r"0x[0-9a-f]+", str(address)), (fixture_id, address)
