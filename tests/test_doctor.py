from __future__ import annotations

import os
from pathlib import Path

import pytest

from ecu_recovery.cli import main
from ecu_recovery.doctor import CheckStatus, render_doctor_report, run_doctor


def _project_fixture(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        """
[project]
name = "legacy-ecu-recovery"
[project.scripts]
ecu-recovery = "ecu_recovery.cli:main"
""".strip(),
        encoding="utf-8",
    )
    required = (
        "docs",
        "samples/synthetic",
        "scripts",
        "src/ecu_recovery/binary",
        "src/ecu_recovery/analysis",
        "src/ecu_recovery/agent",
        "src/ecu_recovery/evidence",
        "src/ecu_recovery/reports",
        "tests",
    )
    for directory in required:
        (root / directory).mkdir(parents=True)


def test_doctor_succeeds_when_optional_ghidra_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _project_fixture(tmp_path)
    monkeypatch.delenv("GHIDRA_HOME", raising=False)
    monkeypatch.setenv("PATH", os.pathsep.join(filter(None, [str(Path(os.__file__).parent)])))

    report = run_doctor(tmp_path)

    ghidra = next(check for check in report.checks if check.name == "Ghidra")
    java = next(check for check in report.checks if check.name == "Java")
    assert ghidra.status is CheckStatus.WARN
    assert java.status is CheckStatus.WARN
    assert report.successful
    assert "Ghidra" in render_doctor_report(report)


def test_doctor_discovers_ghidra_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _project_fixture(tmp_path)
    ghidra_home = tmp_path / "ghidra"
    launcher = ghidra_home / "ghidraRun"
    launcher.parent.mkdir()
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    monkeypatch.setenv("GHIDRA_HOME", str(ghidra_home))

    report = run_doctor(tmp_path)

    ghidra = next(check for check in report.checks if check.name == "Ghidra")
    assert ghidra.status is CheckStatus.PASS
    assert str(launcher) in ghidra.message


def test_doctor_reports_missing_directories(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "legacy-ecu-recovery"\n'
        '[project.scripts]\necu-recovery = "ecu_recovery.cli:main"\n',
        encoding="utf-8",
    )

    report = run_doctor(tmp_path)

    directories = next(check for check in report.checks if check.name == "Directories")
    assert directories.status is CheckStatus.FAIL
    assert not report.successful


def test_doctor_cli_is_readable(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["doctor"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Legacy ECU Recovery doctor" in output
    assert "Summary:" in output
    assert "[PASS] Python:" in output
