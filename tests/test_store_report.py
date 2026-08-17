from pathlib import Path

from ecu_recovery.intake import profile_binary
from ecu_recovery.models import Certainty, FunctionRecord, Hypothesis
from ecu_recovery.report import render_markdown
from ecu_recovery.store import InvestigationStore


def test_round_trip_investigation(tmp_path: Path) -> None:
    firmware = tmp_path / "fixture.rom"
    firmware.write_bytes(bytes(range(128)))
    store = InvestigationStore(tmp_path / "analysis.sqlite3")
    analysis_id = store.save_profile(profile_binary(firmware))
    store.save_function(analysis_id, FunctionRecord(0x8000, "FUN_8000", 24))
    store.save_hypothesis(
        analysis_id,
        Hypothesis(
            subject="FUN_8000",
            claim="possible initialization routine",
            certainty=Certainty.INFERRED,
            confidence=0.65,
            evidence=("first discovered function at ROM base",),
            uncertainty="reset vector has not been confirmed",
        ),
    )

    report = render_markdown(store, analysis_id)

    assert "Unknown (manual selection required)" in report
    assert "`0x8000` — FUN_8000 (24 bytes)" in report
    assert "possible initialization routine" in report
    assert "65%" in report
