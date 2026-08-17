"""Development-graph infrastructure for the Legacy ECU Recovery project.

This package represents, validates, and inspects the dependency DAG in
`ecu-project.graph.yaml`. It is engineering scaffolding for building the
product, not part of the product: it does not launch agents, create worktrees,
schedule work, or run anything in the background.

Typical use:

    from graph import load_graph, ready_nodes, render_status_table

    graph = load_graph()
    print(render_status_table(graph))
    print(ready_nodes(graph))

Note that this graph is Graph A from MASTER_SPEC.md section 8 — the development
graph. It is not the firmware investigation graph and not the firmware
knowledge graph.
"""

from __future__ import annotations

from .loader import (
    DEFAULT_GRAPH_PATH,
    GraphParseError,
    build_graph,
    load_graph,
    load_graph_text,
    parse_yaml_subset,
)
from .models import Graph, Node, NodeStatus, Verification, VerificationKind
from .state import (
    ELIGIBLE_STATES,
    HARD_STOP_STATES,
    IN_FLIGHT_STATES,
    SATISFYING_STATES,
    is_eligible,
    is_hard_stop,
    is_in_flight,
    satisfies_dependency,
)
from .status import (
    blocked_nodes,
    is_blocked,
    is_ready,
    newly_ready_if_passed,
    nodes_with_status,
    obstruction_of,
    passed_nodes,
    ready_nodes,
    render_ready,
    render_status_table,
    unmet_dependencies,
)
from .validator import GraphError, GraphValidationError, collect_errors, is_acyclic, validate

__all__ = [
    "DEFAULT_GRAPH_PATH",
    "ELIGIBLE_STATES",
    "HARD_STOP_STATES",
    "IN_FLIGHT_STATES",
    "SATISFYING_STATES",
    "Graph",
    "GraphError",
    "GraphParseError",
    "GraphValidationError",
    "Node",
    "NodeStatus",
    "Verification",
    "VerificationKind",
    "blocked_nodes",
    "build_graph",
    "collect_errors",
    "is_acyclic",
    "is_blocked",
    "is_eligible",
    "is_hard_stop",
    "is_in_flight",
    "is_ready",
    "load_graph",
    "load_graph_text",
    "newly_ready_if_passed",
    "nodes_with_status",
    "obstruction_of",
    "parse_yaml_subset",
    "passed_nodes",
    "ready_nodes",
    "render_ready",
    "render_status_table",
    "satisfies_dependency",
    "unmet_dependencies",
    "validate",
]
