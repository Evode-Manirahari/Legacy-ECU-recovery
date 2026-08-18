"""Run the corpus: analyze, freeze, reveal, score.

The ordering is the point. `freeze_analysis` touches nothing but
`firmware.stripped`; the answer key is opened afterwards, and the frozen
payload's digest is re-checked once scoring is done, so a run that somehow let
ground truth reach the analyzer would show up as a changed digest rather than
as a flattering number.

Constant probing is the one part that asks the engine targeted questions, and
those questions are derived from the answer key. That is safe for the same
reason reading `firmware.symbols` afterwards is safe: the program has already
been analyzed and frozen, and `search_constant` is a read-only query whose
result cannot alter the analysis. The digest re-check is what makes that a
verified claim instead of an assertion.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..analysis.base import AnalysisError, StaticAnalysisSession
from ..analysis.ghidra import GhidraEngine
from .constants import classify_constants
from .groundtruth import (
    DEFAULT_SAMPLES_ROOT,
    GroundTruthError,
    discover_sample_ids,
    load_ground_truth,
    stripped_firmware,
)
from .models import (
    EVIDENCE_CLASSES,
    SCHEMA_VERSION,
    AggregateMetrics,
    EvaluationRun,
    FixtureResult,
    GateCheck,
    Ratio,
    ToolEnvironment,
    total,
)
from .scoring import score_call_edges, score_functions, scoring_region, warning_summary

#: The gate from prompts/EVAL-STATIC-001.md and EVALS.md, verbatim. Lowering an
#: entry here requires a recorded baseline, a reason, and human approval.
GATE_TARGETS: tuple[tuple[str, str, float], ...] = (
    ("binary_import", "==", 100.0),
    ("serialization", "==", 100.0),
    ("function_discovery_recall", ">=", 95.0),
    ("function_discovery_precision", ">=", 95.0),
    ("call_edge_recall", ">=", 90.0),
    ("unexpected_crashes", "==", 0.0),
)


@dataclass(frozen=True)
class FrozenAnalysis:
    """A serialized analysis result and the digest that pins it."""

    sample_id: str
    payload: dict[str, Any]
    payload_json: str
    digest: str
    round_trip_lossless: bool


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def corpus_relative_source(sample_id: str, samples_root: Path | None = None) -> str:
    """Where the analyzed file sits inside the corpus, not on this disk.

    `ProgramSummary.source_path` is an absolute path, so freezing it verbatim
    would stamp the checkout directory into the payload and its digest. The
    baseline would then only reproduce in the directory that recorded it, and
    any second clone or worktree would report a spurious mismatch.

    Absolute location is not a property of the analysis. What was analyzed is
    already pinned by `executable_sha256`, which is content, so dropping the
    prefix costs no provenance.
    """
    root = (samples_root or DEFAULT_SAMPLES_ROOT).resolve()
    firmware = stripped_firmware(sample_id, samples_root).resolve()
    try:
        return firmware.relative_to(root).as_posix()
    except ValueError:
        # A corpus reached through a symlink or a different root: fall back to
        # the fixture-relative shape rather than leaking an absolute path.
        return f"binaries/{sample_id}/firmware.stripped"


def freeze(
    sample_id: str, session: StaticAnalysisSession, samples_root: Path | None = None
) -> FrozenAnalysis:
    """Export, serialize, and digest. No ground truth is touched here."""
    exported = session.export().as_dict()
    exported["program"]["source_path"] = corpus_relative_source(sample_id, samples_root)
    payload_json = _serialize(exported)
    restored = json.loads(payload_json)
    return FrozenAnalysis(
        sample_id=sample_id,
        payload=restored,
        payload_json=payload_json,
        digest=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        # A round trip that loses nothing is what "serialization success" means:
        # the record that survives JSON is the record the analyzer produced.
        round_trip_lossless=restored == exported and _serialize(restored) == payload_json,
    )


@contextmanager
def frozen_session(
    engine: GhidraEngine, sample_id: str, samples_root: Path | None = None
) -> Iterator[tuple[FrozenAnalysis, StaticAnalysisSession]]:
    firmware = stripped_firmware(sample_id, samples_root)
    with engine.analyze_binary(firmware) as session:
        yield freeze(sample_id, session, samples_root), session


def analyze_only(
    engine: GhidraEngine, sample_id: str, samples_root: Path | None = None
) -> FrozenAnalysis:
    """The analysis half, with no scoring attached.

    Exists so a test can prove the ordering: make the answer key unreadable and
    this must still succeed.
    """
    with frozen_session(engine, sample_id, samples_root) as (frozen, _):
        return frozen


def evaluate_fixture(
    engine: GhidraEngine, sample_id: str, samples_root: Path | None = None
) -> FixtureResult:
    """Score one fixture. A handled analyzer failure is not a crash."""
    try:
        with frozen_session(engine, sample_id, samples_root) as (frozen, session):
            if not frozen.round_trip_lossless:
                return FixtureResult(
                    sample_id=sample_id,
                    imported=True,
                    serialized=False,
                    crashed=False,
                    analysis_digest=frozen.digest,
                    failure="analysis result did not survive a JSON round trip",
                )
            truth = load_ground_truth(sample_id, samples_root)  # <- the reveal
            region = scoring_region(frozen.payload, truth)
            functions = score_functions(frozen.payload, truth, region)
            call_edges = score_call_edges(frozen.payload, truth, region)
            constants = classify_constants(session, frozen.payload, truth)

            after = freeze(sample_id, session, samples_root)
            if after.digest != frozen.digest:
                return FixtureResult(
                    sample_id=sample_id,
                    imported=True,
                    serialized=True,
                    crashed=True,
                    analysis_digest=frozen.digest,
                    failure=(
                        "the analysis result changed while scoring; "
                        f"{frozen.digest} became {after.digest}"
                    ),
                )
            return FixtureResult(
                sample_id=sample_id,
                imported=True,
                serialized=True,
                crashed=False,
                analysis_digest=frozen.digest,
                scoring_region=region,
                functions=functions,
                call_edges=call_edges,
                constants=constants,
                analysis_warnings=warning_summary(frozen.payload),
            )
    except (AnalysisError, GroundTruthError) as error:
        # Reported, typed, and survivable: the harness knows what went wrong.
        return FixtureResult(
            sample_id=sample_id,
            imported=False,
            serialized=False,
            crashed=False,
            analysis_digest="",
            failure=f"{type(error).__name__}: {error}",
        )
    except Exception as error:  # noqa: BLE001 - anything else is a crash, and is counted
        return FixtureResult(
            sample_id=sample_id,
            imported=False,
            serialized=False,
            crashed=True,
            analysis_digest="",
            failure=f"unexpected {type(error).__name__}: {error}",
        )


def describe_environment(
    engine: GhidraEngine, fixtures: Sequence[FixtureResult]
) -> ToolEnvironment:
    del fixtures  # kept for signature stability; versions come from the engine
    try:
        import pyghidra

        pyghidra_version = str(getattr(pyghidra, "__version__", "unknown"))
    except ImportError:
        pyghidra_version = "not installed"
    install = engine.install_dir
    if install is None:
        engine_version = "unavailable"
    else:
        from ..analysis.ghidra import read_ghidra_version

        engine_version = read_ghidra_version(install)
    return ToolEnvironment(
        engine=engine.name,
        engine_version=engine_version,
        analyzer_schema_version=SCHEMA_VERSION,
        python_version=".".join(str(part) for part in sys.version_info[:3]),
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        pyghidra_version=pyghidra_version,
    )


def aggregate(fixtures: Sequence[FixtureResult]) -> AggregateMetrics:
    scored = [item for item in fixtures if item.functions is not None]
    by_evidence = {name: 0 for name in EVIDENCE_CLASSES}
    for item in fixtures:
        if item.constants is None:
            continue
        for name in EVIDENCE_CLASSES:
            by_evidence[name] += item.constants.count(name)
    return AggregateMetrics(
        binary_import=Ratio(sum(1 for item in fixtures if item.imported), len(fixtures)),
        serialization=Ratio(sum(1 for item in fixtures if item.serialized), len(fixtures)),
        function_recall=total([item.functions.recall for item in scored if item.functions]),
        function_precision=total([item.functions.precision for item in scored if item.functions]),
        start_address_accuracy=total(
            [item.functions.start_address_accuracy for item in scored if item.functions]
        ),
        call_edge_recall=total(
            [item.call_edges.recall for item in fixtures if item.call_edges is not None]
        ),
        call_edge_precision=total(
            [item.call_edges.precision for item in fixtures if item.call_edges is not None]
        ),
        unexpected_crashes=sum(1 for item in fixtures if item.crashed),
        constants_recovered=total(
            [item.constants.recovered for item in fixtures if item.constants is not None]
        ),
        constants_by_evidence=by_evidence,
        reported_out_of_scope_functions=sum(
            len(item.functions.reported_out_of_scope) for item in scored if item.functions
        ),
    )


def check_gate(metrics: AggregateMetrics) -> tuple[GateCheck, ...]:
    observed: dict[str, Ratio] = {
        "binary_import": metrics.binary_import,
        "serialization": metrics.serialization,
        "function_discovery_recall": metrics.function_recall,
        "function_discovery_precision": metrics.function_precision,
        "call_edge_recall": metrics.call_edge_recall,
    }
    checks: list[GateCheck] = []
    for metric, comparison, threshold in GATE_TARGETS:
        if metric == "unexpected_crashes":
            checks.append(
                GateCheck(
                    metric=metric,
                    comparison=comparison,
                    threshold=threshold,
                    observed_count=metrics.unexpected_crashes,
                )
            )
            continue
        checks.append(
            GateCheck(
                metric=metric,
                comparison=comparison,
                threshold=threshold,
                observed=observed[metric],
            )
        )
    return tuple(checks)


def run_evaluation(
    engine: GhidraEngine | None = None,
    sample_ids: Sequence[str] | None = None,
    samples_root: Path | None = None,
) -> EvaluationRun:
    """Evaluate every fixture and decide the gate."""
    engine = engine or GhidraEngine()
    ids = tuple(sample_ids) if sample_ids is not None else discover_sample_ids(samples_root)
    fixtures = tuple(evaluate_fixture(engine, sample_id, samples_root) for sample_id in ids)
    metrics = aggregate(fixtures)
    return EvaluationRun(
        environment=describe_environment(engine, fixtures),
        fixtures=fixtures,
        aggregate=metrics,
        gate=check_gate(metrics),
    )
