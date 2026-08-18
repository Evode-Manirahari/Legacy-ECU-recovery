"""The answer key.

Nothing in this module may be called before an analysis result is frozen. That
is the whole protocol from docs/synthetic-lab.md: analyze `firmware.stripped`,
freeze what came back, and only then open the symbols-on build and the
ground-truth JSON. The harness enforces the ordering; this module is kept
separate so the ordering is visible in the import graph rather than buried in a
scoring function.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SAMPLES_ROOT = Path(__file__).resolve().parents[3] / "samples" / "synthetic"


class GroundTruthError(RuntimeError):
    """The answer key is missing, unreadable, or inconsistent with the binary."""


@dataclass(frozen=True)
class GroundTruth:
    """One fixture's hidden expectations, resolved to addresses."""

    sample_id: str
    symbols: dict[int, str]
    expected_functions: tuple[str, ...]
    expected_function_addresses: tuple[int, ...]
    expected_call_edges: tuple[tuple[int, int], ...]
    expected_constants: tuple[int, ...]

    def name_of(self, address: int) -> str:
        return self.symbols.get(address, "<unknown>")


def binaries_root(samples_root: Path | None = None) -> Path:
    return (samples_root or DEFAULT_SAMPLES_ROOT) / "binaries"


def discover_sample_ids(samples_root: Path | None = None) -> tuple[str, ...]:
    """Every fixture the laboratory publishes, in a stable order.

    Read from disk rather than hard-coded, so a fixture added by a later
    DATA-001 revision is scored instead of quietly skipped.
    """
    root = binaries_root(samples_root)
    if not root.is_dir():
        raise GroundTruthError(f"no fixture corpus at {root}")
    return tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))


def stripped_firmware(sample_id: str, samples_root: Path | None = None) -> Path:
    """The only artifact analysis is allowed to see."""
    return binaries_root(samples_root) / sample_id / "firmware.stripped"


def read_text_symbols(sample_id: str, samples_root: Path | None = None) -> dict[int, str]:
    """Address-to-name mapping from the symbols-on build.

    `nm` is used rather than a Mach-O parser because the laboratory documents it
    as the mapping tool, and a second parser would be a second thing to be wrong.
    """
    if shutil.which("nm") is None:
        raise GroundTruthError("nm is required to resolve ground-truth symbol addresses")
    symbols_path = binaries_root(samples_root) / sample_id / "firmware.symbols"
    if not symbols_path.is_file():
        raise GroundTruthError(f"no symbols build at {symbols_path}")
    try:
        completed = subprocess.run(
            ["nm", "-n", str(symbols_path)],
            capture_output=True,
            check=True,
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise GroundTruthError(f"nm failed on {symbols_path}: {error}") from error
    symbols: dict[int, str] = {}
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        address, kind, name = parts
        if kind.lower() != "t":  # text symbols only; `A` is the Mach-O header
            continue
        symbols[int(address, 16)] = name.removeprefix("_")
    if not symbols:
        raise GroundTruthError(f"no text symbols found in {symbols_path}")
    return symbols


def load_ground_truth(sample_id: str, samples_root: Path | None = None) -> GroundTruth:
    """Open the answer key for one fixture. Call only after freezing analysis."""
    root = samples_root or DEFAULT_SAMPLES_ROOT
    path = root / "ground_truth" / f"{sample_id}.json"
    if not path.is_file():
        raise GroundTruthError(f"no ground truth at {path}")
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    symbols = read_text_symbols(sample_id, samples_root)
    by_name = {name: address for address, name in symbols.items()}

    functions = tuple(str(item) for item in payload["expected_functions"])
    missing = [name for name in functions if name not in by_name]
    if missing:
        raise GroundTruthError(
            f"{sample_id}: expected functions {missing} have no symbol address; "
            "the ground-truth file and the symbols build disagree"
        )

    edges: list[tuple[int, int]] = []
    for edge in payload["expected_call_edges"]:
        caller, callee = str(edge["caller"]), str(edge["callee"])
        if caller not in by_name or callee not in by_name:
            raise GroundTruthError(f"{sample_id}: call edge {caller}->{callee} has no address")
        edges.append((by_name[caller], by_name[callee]))

    return GroundTruth(
        sample_id=sample_id,
        symbols=symbols,
        expected_functions=functions,
        expected_function_addresses=tuple(sorted(by_name[name] for name in functions)),
        expected_call_edges=tuple(sorted(set(edges))),
        expected_constants=tuple(int(item) for item in payload.get("expected_constants", ())),
    )
