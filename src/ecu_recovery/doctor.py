"""Local development environment diagnostics."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

MINIMUM_PYTHON = (3, 11)
REQUIRED_DIRECTORIES = (
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


class CheckStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: CheckStatus
    message: str


@dataclass(frozen=True)
class DoctorReport:
    project_root: Path
    checks: tuple[DoctorCheck, ...]

    @property
    def successful(self) -> bool:
        return all(check.status is not CheckStatus.FAIL for check in self.checks)


def find_project_root(start: Path | None = None) -> Path:
    """Find the nearest parent containing this project's configuration."""
    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return current


def _check_python() -> DoctorCheck:
    version = sys.version_info[:3]
    rendered = ".".join(str(part) for part in version)
    if version >= MINIMUM_PYTHON:
        return DoctorCheck("Python", CheckStatus.PASS, f"{rendered} (requires >=3.11)")
    return DoctorCheck("Python", CheckStatus.FAIL, f"{rendered}; Python >=3.11 is required")


def _check_directories(project_root: Path) -> DoctorCheck:
    missing = [path for path in REQUIRED_DIRECTORIES if not (project_root / path).is_dir()]
    if not missing:
        return DoctorCheck(
            "Directories", CheckStatus.PASS, f"all {len(REQUIRED_DIRECTORIES)} required paths exist"
        )
    return DoctorCheck(
        "Directories", CheckStatus.FAIL, "missing required paths: " + ", ".join(missing)
    )


def _check_configuration(project_root: Path) -> DoctorCheck:
    configuration = project_root / "pyproject.toml"
    if not configuration.is_file():
        return DoctorCheck("Configuration", CheckStatus.FAIL, "pyproject.toml was not found")
    try:
        parsed = tomllib.loads(configuration.read_text(encoding="utf-8"))
        project = parsed["project"]
        scripts = project["scripts"]
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as error:
        return DoctorCheck("Configuration", CheckStatus.FAIL, f"invalid pyproject.toml: {error}")
    if project.get("name") != "legacy-ecu-recovery":
        return DoctorCheck("Configuration", CheckStatus.FAIL, "unexpected project name")
    if scripts.get("ecu-recovery") != "ecu_recovery.cli:main":
        return DoctorCheck(
            "Configuration", CheckStatus.FAIL, "ecu-recovery script is not configured"
        )
    return DoctorCheck(
        "Configuration", CheckStatus.PASS, "pyproject.toml and CLI entry point are valid"
    )


def _check_java() -> DoctorCheck:
    executable = shutil.which("java")
    if executable is None:
        return DoctorCheck(
            "Java", CheckStatus.WARN, "not found; required when Ghidra integration is enabled"
        )
    try:
        result = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return DoctorCheck("Java", CheckStatus.WARN, f"found at {executable} but unusable: {error}")
    output = (result.stderr or result.stdout).splitlines()
    version = output[0] if output else "version unavailable"
    if result.returncode != 0:
        return DoctorCheck("Java", CheckStatus.WARN, f"found at {executable} but exited non-zero")
    return DoctorCheck("Java", CheckStatus.PASS, f"{version} ({executable})")


def _ghidra_candidates() -> list[Path]:
    candidates: list[Path] = []
    ghidra_home = os.environ.get("GHIDRA_HOME")
    if ghidra_home:
        home = Path(ghidra_home).expanduser()
        candidates.extend((home / "ghidraRun", home / "support" / "analyzeHeadless"))
    for name in ("ghidraRun", "analyzeHeadless"):
        executable = shutil.which(name)
        if executable:
            candidates.append(Path(executable))
    return candidates


def _check_ghidra() -> DoctorCheck:
    candidates = _ghidra_candidates()
    discovered = next(
        (path.resolve() for path in candidates if path.is_file() and os.access(path, os.X_OK)),
        None,
    )
    if discovered is None:
        return DoctorCheck(
            "Ghidra",
            CheckStatus.WARN,
            "not found (optional for Prompt 1); set GHIDRA_HOME or add it to PATH",
        )
    return DoctorCheck("Ghidra", CheckStatus.PASS, f"discovered at {discovered}")


def run_doctor(project_root: Path | None = None) -> DoctorReport:
    root = find_project_root(project_root)
    return DoctorReport(
        project_root=root,
        checks=(
            _check_python(),
            _check_directories(root),
            _check_configuration(root),
            _check_java(),
            _check_ghidra(),
        ),
    )


def render_doctor_report(report: DoctorReport) -> str:
    lines = ["Legacy ECU Recovery doctor", f"Project root: {report.project_root}", ""]
    lines.extend(f"[{check.status}] {check.name}: {check.message}" for check in report.checks)
    counts = {
        status: sum(check.status is status for check in report.checks) for status in CheckStatus
    }

    lines.extend(
        [
            "",
            "Summary: "
            f"{counts[CheckStatus.PASS]} passed, "
            f"{counts[CheckStatus.WARN]} warning"
            f"{'s' if counts[CheckStatus.WARN] != 1 else ''}, "
            f"{counts[CheckStatus.FAIL]} failed",
        ]
    )
    return "\n".join(lines)
