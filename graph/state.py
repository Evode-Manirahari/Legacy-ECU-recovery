"""Status semantics: what each state means for progression.

Kept separate from `models.py` so the meaning of a state is defined in exactly
one place. Every rule here traces to MASTER_SPEC.md.
"""

from __future__ import annotations

from .models import NodeStatus

#: Only PASSED satisfies a dependency edge.
#:
#: MASTER_SPEC.md section 6: an edge means the prerequisite was *verified*, not
#: that an agent reported done. This is why UNVERIFIED-UNDER-GRAPH does not
#: unlock anything: pre-graph code is candidate implementation, and treating it
#: as a satisfied prerequisite would make the first gate meaningless.
SATISFYING_STATES: frozenset[NodeStatus] = frozenset({NodeStatus.PASSED})

#: States from which a node can still be picked up and executed.
#:
#: UNVERIFIED-UNDER-GRAPH is eligible on purpose. Section 50 step 8 requires
#: re-verifying pre-graph code against each node contract, so those nodes must
#: be able to enter the READY frontier rather than being skipped.
ELIGIBLE_STATES: frozenset[NodeStatus] = frozenset(
    {NodeStatus.PENDING, NodeStatus.UNVERIFIED_UNDER_GRAPH}
)

#: A worker holds the node right now; it is not free to be assigned again.
IN_FLIGHT_STATES: frozenset[NodeStatus] = frozenset(
    {NodeStatus.READY, NodeStatus.RUNNING, NodeStatus.VERIFYING}
)

#: States that stop progression until a human intervenes. A dependent of one of
#: these is obstructed, not merely waiting.
HARD_STOP_STATES: frozenset[NodeStatus] = frozenset(
    {NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.NEEDS_HUMAN}
)


def satisfies_dependency(status: NodeStatus) -> bool:
    """Whether a prerequisite in this state unlocks its dependents."""
    return status in SATISFYING_STATES


def is_eligible(status: NodeStatus) -> bool:
    """Whether a node in this state is still waiting to be executed."""
    return status in ELIGIBLE_STATES


def is_in_flight(status: NodeStatus) -> bool:
    """Whether a worker currently holds this node."""
    return status in IN_FLIGHT_STATES


def is_hard_stop(status: NodeStatus) -> bool:
    """Whether this state obstructs everything downstream of it."""
    return status in HARD_STOP_STATES
