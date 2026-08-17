"""Plain records describing the development dependency graph.

This module is deliberately inert: it defines shape, not policy. Whether a
status satisfies a dependency lives in `state.py`, structural rules live in
`validator.py`, and frontier queries live in `status.py`.

Nothing here knows about YAML, files, or the product itself.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class NodeStatus(StrEnum):
    """The development-node state machine from MASTER_SPEC.md section 11."""

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    #: Pre-graph code that exists but was never verified against a node
    #: contract. It is candidate implementation, never completed graph work.
    UNVERIFIED_UNDER_GRAPH = "UNVERIFIED-UNDER-GRAPH"

    @classmethod
    def parse(cls, raw: str) -> NodeStatus:
        """Convert a spelling from the graph file into a status.

        Raises `ValueError` on anything unrecognized so an invalid state can
        never enter the graph silently.
        """
        try:
            return cls(raw)
        except ValueError:
            valid = ", ".join(status.value for status in cls)
            raise ValueError(f"invalid status {raw!r}; valid statuses are: {valid}") from None


class VerificationKind(StrEnum):
    """How a node is verified.

    `HUMAN` matters operationally: an agent must never self-approve one.
    """

    HUMAN = "human"
    COMMANDS = "commands"
    GATE = "gate"

    @classmethod
    def parse(cls, raw: str) -> VerificationKind:
        try:
            return cls(raw)
        except ValueError:
            valid = ", ".join(kind.value for kind in cls)
            raise ValueError(
                f"invalid verification type {raw!r}; valid types are: {valid}"
            ) from None


@dataclass(frozen=True)
class Verification:
    kind: VerificationKind
    commands: tuple[str, ...] = ()

    @property
    def requires_human(self) -> bool:
        return self.kind is VerificationKind.HUMAN


@dataclass(frozen=True)
class Node:
    """One bounded engineering objective."""

    id: str
    title: str
    depends_on: tuple[str, ...] = ()
    status: NodeStatus = NodeStatus.PENDING
    worker: str | None = None
    prompt: str | None = None
    allowed_paths: tuple[str, ...] = ()
    verification: Verification | None = None
    retry_budget: int | None = None
    note: str | None = None


@dataclass(frozen=True)
class Graph:
    """A whole development graph.

    Node order is the order declared in the graph file, so rendered output is
    stable and reviewable rather than sorted into something unrecognizable.
    """

    project_id: str
    version: str
    nodes: Mapping[str, Node] = field(default_factory=dict)

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes.values())

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.nodes

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self.nodes)

    def node(self, node_id: str) -> Node:
        """Look up one node, failing loudly on an unknown id."""
        try:
            return self.nodes[node_id]
        except KeyError:
            raise KeyError(f"unknown node {node_id!r}") from None

    def dependencies_of(self, node_id: str) -> tuple[str, ...]:
        """Direct prerequisites of a node."""
        return self.node(node_id).depends_on

    def dependents_of(self, node_id: str) -> tuple[str, ...]:
        """Nodes that directly depend on this one."""
        self.node(node_id)
        return tuple(node.id for node in self if node_id in node.depends_on)

    def with_status(self, node_id: str, status: NodeStatus) -> Graph:
        """Return a copy where one node has a different status.

        Used to answer "what becomes ready if this passes?" without mutating
        the loaded graph, so a query can never corrupt the recorded state.
        """
        current = self.node(node_id)
        updated = dict(self.nodes)
        updated[node_id] = Node(
            id=current.id,
            title=current.title,
            depends_on=current.depends_on,
            status=status,
            worker=current.worker,
            prompt=current.prompt,
            allowed_paths=current.allowed_paths,
            verification=current.verification,
            retry_budget=current.retry_budget,
            note=current.note,
        )
        return Graph(project_id=self.project_id, version=self.version, nodes=updated)
