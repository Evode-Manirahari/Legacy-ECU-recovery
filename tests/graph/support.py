"""Helpers for building small graphs in tests.

Deliberately named `support` rather than `conftest`. pytest puts this directory
on `sys.path`, so a `conftest` here would shadow `tests/conftest` for sibling
tests that import it by name — and an `__init__.py` would make this directory a
package called `graph`, shadowing the real one. A unique module name avoids
both collisions.

The `graph` package itself is reachable because `pyproject.toml` puts the
repository root on pytest's `pythonpath`.
"""

from __future__ import annotations


def graph_text(*nodes: str, project: str = "test-graph") -> str:
    """Assemble a small graph file from node blocks, for negative tests."""
    body = "\n".join(nodes)
    return f'project:\n  id: {project}\n  version: "1.0"\n\nnodes:\n{body}\n'


def node_block(
    node_id: str,
    *,
    status: str = "PENDING",
    depends_on: tuple[str, ...] = (),
    title: str | None = None,
) -> str:
    """Render one node block at the indentation the parser expects."""
    lines = [f"  {node_id}:", f"    title: {title or node_id} title"]
    if depends_on:
        lines.append("    depends_on:")
        lines.extend(f"      - {dependency}" for dependency in depends_on)
    else:
        lines.append("    depends_on: []")
    lines.append(f"    status: {status}")
    return "\n".join(lines)
