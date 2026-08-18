"""Structural validation of a development graph.

A graph that governs what work may start has to fail loudly rather than
degrade. Every problem found is collected and reported together, because
fixing one broken edge at a time across several runs wastes the reviewer's
attention.

Where each rule is enforced:

| Rule | Enforced by |
|---|---|
| invalid status value | `NodeStatus.parse` during loading |
| duplicate node id | duplicate-key check during parsing |
| unknown dependency | this module |
| self-dependency | this module |
| cycle | this module |
| unsafe ownership overlap | this module |

The first two are structurally impossible to represent once a `Graph` exists —
a status is an enum and node ids are mapping keys — so they are caught at the
boundary where text becomes data.
"""

from __future__ import annotations

from .models import Graph


class GraphError(ValueError):
    """Base class for every graph failure, including parse failures."""


class GraphValidationError(GraphError):
    """A graph is structurally invalid.

    Carries every problem found, not just the first.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        joined = "\n  - ".join(self.errors)
        count = len(self.errors)
        noun = "problem" if count == 1 else "problems"
        super().__init__(f"graph is invalid ({count} {noun}):\n  - {joined}")


def _find_unknown_dependencies(graph: Graph) -> list[str]:
    errors: list[str] = []
    for node in graph:
        for dependency in node.depends_on:
            if dependency not in graph:
                errors.append(f"{node.id}: depends on unknown node {dependency!r}")
    return errors


def _find_self_dependencies(graph: Graph) -> list[str]:
    return [f"{node.id}: depends on itself" for node in graph if node.id in node.depends_on]


def _find_cycles(graph: Graph) -> list[str]:
    """Depth-first search reporting each cycle as the path that closes it."""
    visited: set[str] = set()
    on_stack: list[str] = []
    stack_set: set[str] = set()
    errors: list[str] = []
    reported: set[frozenset[str]] = set()

    def walk(node_id: str) -> None:
        if node_id in stack_set:
            start = on_stack.index(node_id)
            cycle = [*on_stack[start:], node_id]
            signature = frozenset(cycle)
            if signature not in reported:
                reported.add(signature)
                errors.append("cycle detected: " + " -> ".join(cycle))
            return
        if node_id in visited:
            return
        visited.add(node_id)
        on_stack.append(node_id)
        stack_set.add(node_id)
        for dependency in graph.node(node_id).depends_on:
            # Unknown and self dependencies are reported separately; skipping
            # them here keeps cycle messages about real cycles.
            if dependency in graph and dependency != node_id:
                walk(dependency)
        on_stack.pop()
        stack_set.discard(node_id)

    for node in graph:
        walk(node.id)
    return errors


def _dependency_closure(graph: Graph, node_id: str) -> set[str]:
    """Every node this one transitively depends on."""
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        for dependency in graph.node(stack.pop()).depends_on:
            if dependency in graph and dependency not in seen:
                seen.add(dependency)
                stack.append(dependency)
    return seen


def can_run_concurrently(graph: Graph, first: str, second: str) -> bool:
    """Whether two nodes could ever be assigned at the same time.

    Ordered nodes cannot collide: if one depends on the other, even
    transitively, the second never starts until the first has passed. Only
    independent nodes need disjoint ownership.
    """
    if first == second:
        return False
    return first not in _dependency_closure(graph, second) and second not in _dependency_closure(
        graph, first
    )


def _pattern_segments(pattern: str) -> tuple[str, ...]:
    """Reduce an allowed-path pattern to the directory prefix it governs.

    `a/b/**` and `a/b` both govern everything under `a/b`; a bare file path
    governs only itself. Comparing segment tuples keeps `tests/test_a.py` from
    looking like a prefix of `tests/test_ab.py`.
    """
    trimmed = pattern.strip().rstrip("/")
    if trimmed.endswith("/**"):
        trimmed = trimmed[: -len("/**")]
    elif trimmed == "**":
        trimmed = ""
    return tuple(part for part in trimmed.split("/") if part)


def paths_overlap(first: str, second: str) -> bool:
    """Whether two allowed-path patterns can match a common file.

    True when one governs a location at or inside the other, which is exactly
    the case where two workers could edit the same file.
    """
    left, right = _pattern_segments(first), _pattern_segments(second)
    shared = min(len(left), len(right))
    return left[:shared] == right[:shared]


def find_ownership_overlaps(graph: Graph) -> list[str]:
    """Report ownership shared between nodes that may run concurrently.

    This is what stops a parallel fan-out from having two workers edit the same
    file. It is deliberately narrow: it compares declared patterns and says
    nothing about whether a file exists.
    """
    overlaps: list[str] = []
    nodes = list(graph)
    for index, first in enumerate(nodes):
        for second in nodes[index + 1 :]:
            if not can_run_concurrently(graph, first.id, second.id):
                continue
            for left in first.allowed_paths:
                for right in second.allowed_paths:
                    if paths_overlap(left, right):
                        overlaps.append(
                            f"{first.id} and {second.id} may run concurrently but both own "
                            f"overlapping paths: {left!r} and {right!r}"
                        )
    return overlaps


def collect_errors(graph: Graph) -> list[str]:
    """Return every structural problem in the graph, in a stable order."""
    return [
        *_find_unknown_dependencies(graph),
        *_find_self_dependencies(graph),
        *_find_cycles(graph),
        *find_ownership_overlaps(graph),
    ]


def validate(graph: Graph) -> Graph:
    """Raise `GraphValidationError` if the graph is not a usable DAG."""
    errors = collect_errors(graph)
    if errors:
        raise GraphValidationError(errors)
    return graph


def is_acyclic(graph: Graph) -> bool:
    """Whether the graph contains no dependency cycle."""
    return not _find_cycles(graph)
