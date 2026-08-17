from __future__ import annotations

import ctypes
import hashlib
import json
import platform
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


def test_manifest_separates_investigator_artifacts_from_ground_truth() -> None:
    manifest = load_json(MANIFEST)
    assert manifest["investigator_visible"] == ["binaries/<sample_id>/firmware.stripped"]
    assert len(manifest["samples"]) == 6
    assert len(set(manifest["samples"])) == 6


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
