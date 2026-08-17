"""The `ecu-recovery graph` subcommand.

The subcommand is read-only by design: inspecting the graph must never change
node status, because status is what decides whether work may start.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from support import graph_text, node_block

from ecu_recovery.cli import main


def test_status_lists_every_node(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["graph", "status"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "SPEC-001" in output
    assert "PASSED" in output
    assert "GATE-STATIC-MVP" in output
    assert len(output.strip().splitlines()) == 11


def test_status_explains_why_a_node_is_waiting(capsys: pytest.CaptureFixture[str]) -> None:
    main(["graph", "status"])

    assert "waiting on GRAPH-001" in capsys.readouterr().out


def test_ready_reports_the_frontier(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["graph", "ready"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "No nodes are ready."


def test_ready_lists_an_open_frontier(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    graph_file = tmp_path / "graph.yaml"
    graph_file.write_text(
        graph_text(
            node_block("ROOT-001", status="PASSED"),
            node_block("NEXT-001", depends_on=("ROOT-001",)),
        ),
        encoding="utf-8",
    )

    exit_code = main(["graph", "ready", "--graph-file", str(graph_file)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "NEXT-001" in output
    assert "ROOT-001" not in output


def test_a_malformed_graph_exits_with_an_error(tmp_path: Path) -> None:
    graph_file = tmp_path / "broken.yaml"
    graph_file.write_text(
        graph_text(node_block("A-001", depends_on=("GHOST-001",))), encoding="utf-8"
    )

    with pytest.raises(SystemExit) as caught:
        main(["graph", "status", "--graph-file", str(graph_file)])

    assert caught.value.code == 2


def test_a_missing_graph_file_exits_with_an_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["graph", "status", "--graph-file", str(tmp_path / "absent.yaml")])

    assert caught.value.code == 2


def test_graph_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        main(["graph"])
