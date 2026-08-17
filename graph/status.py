"""Frontier queries over a validated development graph.

Answers the questions MASTER_SPEC.md section 20.1 requires: what exists, what
depends on what, what is ready, what is blocked, what has passed, and what
would open up if a given node passed.

All queries are pure. Nothing here mutates the loaded graph or touches disk.
"""

from __future__ import annotations

from .models import Graph, NodeStatus
from .state import is_eligible, is_hard_stop, satisfies_dependency

#: Width of the id column in rendered tables, sized for the longest current
#: node id (`INTEGRATION-STATIC-001`) plus separation.
_ID_COLUMN = 26


def unmet_dependencies(graph: Graph, node_id: str) -> tuple[str, ...]:
    """Prerequisites of a node that have not passed."""
    return tuple(
        dependency
        for dependency in graph.dependencies_of(node_id)
        if not satisfies_dependency(graph.node(dependency).status)
    )


def is_ready(graph: Graph, node_id: str) -> bool:
    """Whether a node can be assigned to a worker right now.

    Ready means the node still needs doing and every prerequisite has actually
    passed. A node already in flight is not ready; someone holds it.
    """
    node = graph.node(node_id)
    if not is_eligible(node.status):
        return False
    return not unmet_dependencies(graph, node_id)


def obstruction_of(graph: Graph, node_id: str) -> tuple[str, ...]:
    """Prerequisites that stop this node from ever becoming ready as-is.

    Distinguishes *waiting* from *obstructed*. A node whose prerequisite is
    merely pending is waiting, and the graph will free it in time. A node whose
    prerequisite failed, is blocked, or needs a human will never free itself.
    """
    obstructions: list[str] = []
    seen: set[str] = set()

    def walk(current: str) -> None:
        for dependency in graph.dependencies_of(current):
            if dependency in seen or dependency not in graph:
                continue
            seen.add(dependency)
            if is_hard_stop(graph.node(dependency).status):
                obstructions.append(dependency)
                continue
            walk(dependency)

    walk(node_id)
    return tuple(obstructions)


def is_blocked(graph: Graph, node_id: str) -> bool:
    """Whether a node is stopped rather than merely waiting its turn."""
    if graph.node(node_id).status is NodeStatus.BLOCKED:
        return True
    return bool(obstruction_of(graph, node_id))


def ready_nodes(graph: Graph) -> tuple[str, ...]:
    """The executable frontier, in declaration order."""
    return tuple(node.id for node in graph if is_ready(graph, node.id))


def blocked_nodes(graph: Graph) -> tuple[str, ...]:
    """Nodes that cannot proceed without intervention."""
    return tuple(node.id for node in graph if is_blocked(graph, node.id))


def passed_nodes(graph: Graph) -> tuple[str, ...]:
    """Nodes whose verification actually passed."""
    return tuple(node.id for node in graph if node.status is NodeStatus.PASSED)


def nodes_with_status(graph: Graph, status: NodeStatus) -> tuple[str, ...]:
    return tuple(node.id for node in graph if node.status is status)


def newly_ready_if_passed(graph: Graph, node_id: str) -> tuple[str, ...]:
    """Which nodes would join the frontier if `node_id` passed.

    Answered by simulating the pass on a copy, so asking the question never
    changes the recorded state.
    """
    before = set(ready_nodes(graph))
    after = ready_nodes(graph.with_status(node_id, NodeStatus.PASSED))
    return tuple(candidate for candidate in after if candidate not in before)


def render_status_table(graph: Graph) -> str:
    """One line per node: id, status, and why it is not ready when relevant."""
    lines: list[str] = []
    for node in graph:
        line = f"{node.id.ljust(_ID_COLUMN)}{node.status.value}"
        if is_ready(graph, node.id):
            line += "  (ready)"
        else:
            obstructions = obstruction_of(graph, node.id)
            if obstructions:
                line += f"  (blocked by {', '.join(obstructions)})"
            elif is_eligible(node.status):
                unmet = unmet_dependencies(graph, node.id)
                if unmet:
                    line += f"  (waiting on {', '.join(unmet)})"
        lines.append(line)
    return "\n".join(lines)


def render_ready(graph: Graph) -> str:
    """The frontier alone, for deciding what to assign next."""
    ready = ready_nodes(graph)
    if not ready:
        return "No nodes are ready."
    return "\n".join(f"{node_id.ljust(_ID_COLUMN)}{graph.node(node_id).title}" for node_id in ready)
