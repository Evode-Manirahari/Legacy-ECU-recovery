"""Regenerate the committed integration report.

    uv run python tests/integration/record_artifact.py

A test asserts the committed artifact matches what the flow produces, so
recording is a deliberate act rather than a side effect of running the suite.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from integration_support import (  # noqa: E402
    FIXTURES,
    REPORT_PATH,
    FlowResult,
    render_report,
    run_static_flow,
)


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="ecu-integration-"))
    results: list[FlowResult] = [
        run_static_flow(sample_id, workspace / f"{sample_id}.sqlite3") for sample_id in FIXTURES
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(results), encoding="utf-8")
    print(f"flow={'PASS' if all(item.ok for item in results) else 'FAIL'}")
    print(f"report={REPORT_PATH}")
    return 0 if all(item.ok for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
