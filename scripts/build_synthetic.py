#!/usr/bin/env python3
"""Rebuild the complete synthetic firmware dataset deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = PROJECT_ROOT / "samples" / "synthetic"
DEFAULT_OUTPUT_ROOT = DATASET_ROOT / "binaries"

COMMON_FLAGS = (
    "-std=c11",
    "-arch",
    "x86_64",
    "-mmacosx-version-min=13.0",
    "-O1",
    "-Wall",
    "-Wextra",
    "-Werror",
    "-fno-inline",
    "-fno-omit-frame-pointer",
    "-fno-stack-protector",
)


class BuildError(RuntimeError):
    """The local toolchain could not produce a valid fixture."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update({"LC_ALL": "C", "SOURCE_DATE_EPOCH": "0", "ZERO_AR_DATE": "1"})
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=30,
    )
    if check and result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise BuildError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BuildError(f"expected a JSON object: {path}")
    return payload


def normalized_symbols(nm: str, binary: Path) -> set[str]:
    result = run([nm, "-j", str(binary)], check=False)
    if result.returncode not in (0, 1):
        raise BuildError(f"nm failed for {binary}: {result.stderr.strip()}")
    return {line.strip().removeprefix("_") for line in result.stdout.splitlines() if line.strip()}


def validate_host() -> None:
    if platform.system() != "Darwin" or platform.machine() != "x86_64":
        raise BuildError(
            "synthetic dataset v1 targets x86_64-apple-darwin; "
            f"current host is {platform.machine()}-{platform.system().lower()}"
        )


def validate_metadata(metadata: dict[str, Any], expected_id: str) -> None:
    required = {
        "schema_version",
        "sample_id",
        "title",
        "source",
        "probe_parameters",
        "expected_functions",
        "expected_function_roles",
        "classification_functions",
        "expected_call_edges",
        "expected_constants",
        "expected_behavior",
    }
    missing = sorted(required - metadata.keys())
    if missing:
        raise BuildError(f"{expected_id} metadata is missing: {', '.join(missing)}")
    if metadata["schema_version"] != 1 or metadata["sample_id"] != expected_id:
        raise BuildError(f"{expected_id} metadata identity is invalid")
    parameters = metadata["probe_parameters"]
    if not isinstance(parameters, list) or len(parameters) != 3:
        raise BuildError(f"{expected_id} must declare exactly three probe parameters")
    if set(metadata["expected_function_roles"]) != set(metadata["expected_functions"]):
        raise BuildError(f"{expected_id} must define a role for every expected function")
    if not set(metadata["classification_functions"]) <= set(metadata["expected_functions"]):
        raise BuildError(f"{expected_id} classification functions must be expected functions")
    for case in metadata["expected_behavior"]:
        if list(case["inputs"].keys()) != parameters:
            raise BuildError(f"{expected_id} behavior input order does not match probe parameters")
        if not isinstance(case["output"], int):
            raise BuildError(f"{expected_id} behavior output must be an integer")


def display_command(command: list[str]) -> list[str]:
    return [argument.replace(str(PROJECT_ROOT), "${PROJECT_ROOT}") for argument in command]


def build_sample(
    sample_id: str,
    *,
    output_root: Path,
    clang: str,
    strip: str,
    nm: str,
    compiler_version: str,
) -> dict[str, str]:
    metadata_path = DATASET_ROOT / "ground_truth" / f"{sample_id}.json"
    metadata = load_json(metadata_path)
    validate_metadata(metadata, sample_id)
    source = DATASET_ROOT / metadata["source"]
    if not source.is_file():
        raise BuildError(f"source does not exist: {source}")

    sample_output = output_root / sample_id
    sample_output.mkdir(parents=True, exist_ok=True)
    symbols_on = sample_output / "firmware.symbols"
    symbols_stripped = sample_output / "firmware.stripped"
    behavior_library = sample_output / "behavior.dylib"
    build_record = sample_output / "build.json"

    analysis_command = [
        clang,
        *COMMON_FLAGS,
        "-fno-pie",
        str(source),
        "-Wl,-no_pie",
        "-Wl,-no_uuid",
        "-o",
        str(symbols_on),
    ]
    behavior_command = [
        clang,
        *COMMON_FLAGS,
        "-DSAMPLE_BEHAVIOR_LIBRARY",
        "-dynamiclib",
        "-fvisibility=hidden",
        str(source),
        "-Wl,-install_name,@rpath/behavior.dylib",
        "-Wl,-no_uuid",
        "-o",
        str(behavior_library),
    ]

    run(analysis_command)
    run([str(symbols_on)])
    shutil.copyfile(symbols_on, symbols_stripped)
    symbols_stripped.chmod(symbols_on.stat().st_mode)
    run([strip, "-S", "-x", str(symbols_stripped)])
    run([str(symbols_stripped)])
    run(behavior_command)

    expected_functions = set(metadata["expected_functions"])
    symbols_on_names = normalized_symbols(nm, symbols_on)
    missing_functions = sorted(expected_functions - symbols_on_names)
    if missing_functions:
        raise BuildError(f"{sample_id} symbols build is missing: {', '.join(missing_functions)}")
    functions_that_must_be_hidden = expected_functions - {"main"}
    leaked_functions = sorted(
        functions_that_must_be_hidden & normalized_symbols(nm, symbols_stripped)
    )
    if leaked_functions:
        raise BuildError(f"{sample_id} stripped build leaked: {', '.join(leaked_functions)}")

    record = {
        "schema_version": 1,
        "sample_id": sample_id,
        "architecture": "x86_64-apple-darwin",
        "compiler": compiler_version,
        "source_sha256": sha256(source),
        "commands": {
            "symbols_on": display_command(analysis_command),
            "strip": [strip, "-S", "-x", "firmware.stripped"],
            "behavior_library": display_command(behavior_command),
        },
        "artifacts": {
            "firmware.symbols": sha256(symbols_on),
            "firmware.stripped": sha256(symbols_stripped),
            "behavior.dylib": sha256(behavior_library),
        },
    }
    build_record.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record["artifacts"]


def build_dataset(output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, dict[str, str]]:
    validate_host()
    clang = shutil.which("clang")
    strip = shutil.which("strip")
    nm = shutil.which("nm")
    if not clang or not strip or not nm:
        raise BuildError("clang, strip, and nm must all be available on PATH")
    compiler_version = run([clang, "--version"]).stdout.splitlines()[0]
    manifest = load_json(DATASET_ROOT / "manifest.json")
    if manifest.get("schema_version") != 1:
        raise BuildError("unsupported synthetic manifest schema")

    output_root.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, str]] = {}
    for sample_id in manifest["samples"]:
        results[sample_id] = build_sample(
            sample_id,
            output_root=output_root,
            clang=clang,
            strip=strip,
            nm=nm,
            compiler_version=compiler_version,
        )
        print(f"built {sample_id}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="artifact destination (defaults to samples/synthetic/binaries)",
    )
    arguments = parser.parse_args()
    try:
        build_dataset(arguments.output_root.expanduser().resolve())
    except (BuildError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
