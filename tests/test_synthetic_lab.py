from __future__ import annotations

import ctypes
import hashlib
import json
import platform
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = PROJECT_ROOT / "samples" / "synthetic"
MANIFEST = DATASET_ROOT / "manifest.json"
ON_BUILD_HOST = platform.system() == "Darwin" and platform.machine() == "x86_64"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample_ids() -> list[str]:
    return list(load_json(MANIFEST)["samples"])


@pytest.mark.parametrize("sample_id", sample_ids())
def test_sample_has_complete_ground_truth_and_artifacts(sample_id: str) -> None:
    metadata_path = DATASET_ROOT / "ground_truth" / f"{sample_id}.json"
    metadata = load_json(metadata_path)
    assert metadata["schema_version"] == 1
    assert metadata["sample_id"] == sample_id
    assert len(metadata["probe_parameters"]) == 3
    assert metadata["expected_functions"]
    assert set(metadata["expected_function_roles"]) == set(metadata["expected_functions"])
    assert set(metadata["classification_functions"]) <= set(metadata["expected_functions"])
    assert metadata["expected_call_edges"]
    assert metadata["expected_behavior"]
    assert (DATASET_ROOT / metadata["source"]).is_file()

    binary_root = DATASET_ROOT / "binaries" / sample_id
    build = load_json(binary_root / "build.json")
    assert build["sample_id"] == sample_id
    assert build["architecture"] == "x86_64-apple-darwin"
    for artifact, expected_hash in build["artifacts"].items():
        artifact_path = binary_root / artifact
        assert artifact_path.is_file()
        assert file_sha256(artifact_path) == expected_hash


#: The eight fixture categories the DATA-001 contract requires, mapped to the
#: sample that covers each. Asserted by id so a renamed or dropped fixture fails
#: loudly rather than silently reducing coverage.
REQUIRED_CATEGORIES = {
    "temperature threshold controller": "temperature_controller_v1",
    "RPM-like calculation": "rpm_calculation_v1",
    "one-dimensional lookup table": "lookup_1d_v1",
    "two-dimensional lookup table": "lookup_2d_v1",
    "state machine": "state_machine_v1",
    "multi-function call graph": "multi_function_pipeline_v1",
    "integer/bit-mask manipulation": "bitmask_manipulation_v1",
    "timer-like counter logic": "timer_counter_v1",
}


def test_manifest_separates_investigator_artifacts_from_ground_truth() -> None:
    manifest = load_json(MANIFEST)
    assert manifest["investigator_visible"] == ["binaries/<sample_id>/firmware.stripped"]
    assert len(manifest["samples"]) == len(set(manifest["samples"]))


def test_every_required_fixture_category_is_present() -> None:
    """DATA-001 requires all eight categories, not merely eight samples."""
    declared = set(sample_ids())

    missing = {
        category: sample
        for category, sample in REQUIRED_CATEGORIES.items()
        if sample not in declared
    }

    assert not missing, f"missing fixture categories: {missing}"
    assert declared == set(REQUIRED_CATEGORIES.values())


@pytest.mark.parametrize("sample_id", sample_ids())
def test_sample_preserves_every_contract_field(sample_id: str) -> None:
    """The contract's 'for every fixture preserve' list, checked per sample."""
    metadata = load_json(DATASET_ROOT / "ground_truth" / f"{sample_id}.json")
    build = load_json(DATASET_ROOT / "binaries" / sample_id / "build.json")

    assert metadata["expected_constants"], "expected constants must not be empty"
    assert metadata["expected_call_edges"], "expected relationships must not be empty"
    assert build["compiler"].strip(), "compiler identity must be recorded"
    assert build["commands"]["symbols_on"], "compiler flags must be recorded"
    assert build["source_sha256"]
    for artifact in ("firmware.symbols", "firmware.stripped", "behavior.dylib"):
        assert artifact in build["artifacts"], f"{artifact} must be recorded"


def instruction_immediates(binary_path: Path) -> set[int]:
    """Immediate operands in the disassembly, at whatever width they encode."""
    result = subprocess.run(
        ["otool", "-tvV", str(binary_path)], capture_output=True, check=False, text=True, timeout=30
    )
    return {int(match, 16) for match in re.findall(r"\$0x([0-9a-f]+)", result.stdout)}


@pytest.mark.skipif(not ON_BUILD_HOST, reason="constant recovery inspects a Mach-O build")
@pytest.mark.parametrize("sample_id", sample_ids())
def test_expected_constants_are_actually_recoverable(sample_id: str) -> None:
    """Ground truth must not claim a constant the binary does not contain.

    A claimed-but-absent constant scores as a tool failure during evaluation
    when the fault is really in the fixture. A constant is recoverable if the
    compiler emitted it either as an instruction operand or as data: small
    values become one-byte immediates, table entries land in `__const`, and
    which one happens is the compiler's choice, not the fixture author's.
    """
    metadata = load_json(DATASET_ROOT / "ground_truth" / f"{sample_id}.json")
    binary_path = DATASET_ROOT / "binaries" / sample_id / "firmware.symbols"
    immediates = instruction_immediates(binary_path)
    data = binary_path.read_bytes()

    unrecoverable = [
        value
        for value in metadata["expected_constants"]
        if value not in immediates and struct.pack("<i", value) not in data
    ]

    assert not unrecoverable, f"{sample_id} claims absent constants: {unrecoverable}"


@pytest.mark.skipif(not ON_BUILD_HOST, reason="v1 behavior artifacts require x86_64 macOS")
@pytest.mark.parametrize("sample_id", sample_ids())
def test_behavior_library_matches_ground_truth(sample_id: str) -> None:
    metadata = load_json(DATASET_ROOT / "ground_truth" / f"{sample_id}.json")
    library_path = DATASET_ROOT / "binaries" / sample_id / "behavior.dylib"
    library = ctypes.CDLL(str(library_path))
    invoke = library.sample_invoke
    invoke.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
    invoke.restype = ctypes.c_int32

    parameters = metadata["probe_parameters"]
    for case in metadata["expected_behavior"]:
        arguments = [case["inputs"][parameter] for parameter in parameters]
        assert invoke(*arguments) == case["output"], case


@pytest.mark.skipif(not ON_BUILD_HOST, reason="v1 executables require x86_64 macOS")
@pytest.mark.parametrize("sample_id", sample_ids())
def test_both_analysis_builds_pass_embedded_self_tests(sample_id: str) -> None:
    binary_root = DATASET_ROOT / "binaries" / sample_id
    for artifact in ("firmware.symbols", "firmware.stripped"):
        result = subprocess.run(
            [str(binary_root / artifact)], capture_output=True, check=False, timeout=5
        )
        assert result.returncode == 0, f"{sample_id}/{artifact} returned {result.returncode}"


@pytest.mark.skipif(not ON_BUILD_HOST, reason="v1 rebuild requires x86_64 macOS tools")
def test_rebuild_is_byte_reproducible(tmp_path: Path) -> None:
    rebuilt_root = tmp_path / "binaries"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "build_synthetic.py"),
            "--output-root",
            str(rebuilt_root),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr

    for sample_id in sample_ids():
        committed = load_json(DATASET_ROOT / "binaries" / sample_id / "build.json")
        rebuilt = load_json(rebuilt_root / sample_id / "build.json")
        assert rebuilt["artifacts"] == committed["artifacts"]
