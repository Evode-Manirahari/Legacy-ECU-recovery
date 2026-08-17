"""Read `ecu-project.graph.yaml` into a `Graph`.

## Why this parses YAML itself

The repository has no mandatory third-party runtime dependency, which is a
recorded architectural property, and `pyproject.toml` is outside GRAPH-001's
ownership. So instead of pulling in PyYAML, this module reads the small, fixed
subset of YAML the graph file actually uses.

The parser is deliberately strict. Anything outside that subset — tabs, flow
style, anchors, block scalars, duplicate keys — raises rather than being
guessed at. The failure mode is "refuses to load", never "loads something
different from what the file says", which is the only acceptable behaviour for
a file that defines what work is allowed to start.

Swapping in PyYAML later is a small change confined to `parse_yaml_subset`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Graph, Node, NodeStatus, Verification, VerificationKind
from .validator import GraphError, validate

DEFAULT_GRAPH_PATH = Path(__file__).resolve().parents[1] / "ecu-project.graph.yaml"

_KEY_PATTERN = re.compile(r"^(?P<key>[^:]+):(?:\s+(?P<value>.*))?$")
_INT_PATTERN = re.compile(r"^-?\d+$")
_REJECTED_SYNTAX = (
    ("\t", "tabs are not valid YAML indentation"),
    ("&", "anchors are not supported"),
    ("*", "aliases are not supported"),
)


class GraphParseError(GraphError):
    """The graph file is not readable as the supported YAML subset."""


@dataclass(frozen=True)
class _Line:
    number: int
    indent: int
    text: str


def _scan(text: str) -> list[_Line]:
    """Strip blanks and comments, and reject syntax the parser cannot honour."""
    lines: list[_Line] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw:
            raise GraphParseError(f"line {number}: tabs are not valid YAML indentation")
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in {"---", "..."}:
            raise GraphParseError(f"line {number}: multi-document YAML is not supported")
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append(_Line(number=number, indent=indent, text=stripped))
    return lines


def _parse_scalar(raw: str, number: int) -> Any:
    """Convert one scalar, rejecting constructs the parser cannot honour."""
    value = raw.strip()
    if not value:
        return None
    if value[0] in "\"'":
        if len(value) < 2 or value[-1] != value[0]:
            raise GraphParseError(f"line {number}: unterminated quoted string")
        return value[1:-1]
    # Only bare scalars may carry a trailing comment; a quoted string keeps its
    # '#' verbatim, which is why this runs after the quoted branch.
    comment = value.find(" #")
    if comment != -1:
        value = value[:comment].strip()
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value.startswith(("[", "{")):
        raise GraphParseError(
            f"line {number}: inline flow collections are not supported; use block style"
        )
    if value.startswith(("|", ">")):
        raise GraphParseError(f"line {number}: block scalars are not supported")
    for token, reason in _REJECTED_SYNTAX:
        if value.startswith(token):
            raise GraphParseError(f"line {number}: {reason}")
    if value in {"null", "~"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if _INT_PATTERN.match(value):
        return int(value)
    return value


def _parse_block(lines: list[_Line], index: int, indent: int) -> tuple[Any, int]:
    """Parse one indented block, returning its value and the next line index."""
    if lines[index].text.startswith("- "):
        return _parse_sequence(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_sequence(lines: list[_Line], index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines) and lines[index].indent == indent:
        line = lines[index]
        if not line.text.startswith("- "):
            break
        items.append(_parse_scalar(line.text[2:], line.number))
        index += 1
    return items, index


def _parse_mapping(lines: list[_Line], index: int, indent: int) -> tuple[dict[str, Any], int]:
    mapping: dict[str, Any] = {}
    while index < len(lines) and lines[index].indent == indent:
        line = lines[index]
        if line.text.startswith("- "):
            break
        match = _KEY_PATTERN.match(line.text)
        if match is None:
            raise GraphParseError(f"line {line.number}: expected 'key: value', found {line.text!r}")
        key = match.group("key").strip()
        if key in mapping:
            raise GraphParseError(f"line {line.number}: duplicate key {key!r}")
        inline = match.group("value")
        index += 1
        if inline:
            mapping[key] = _parse_scalar(inline, line.number)
            continue
        # No inline value: either a nested block indented further, or an
        # explicitly empty value.
        if index < len(lines) and lines[index].indent > indent:
            mapping[key], index = _parse_block(lines, index, lines[index].indent)
        else:
            mapping[key] = None
    return mapping, index


def parse_yaml_subset(text: str) -> dict[str, Any]:
    """Parse the supported YAML subset into plain Python data."""
    lines = _scan(text)
    if not lines:
        return {}
    if lines[0].indent != 0:
        raise GraphParseError(f"line {lines[0].number}: document must start at column 0")
    value, index = _parse_block(lines, 0, 0)
    if index != len(lines):
        raise GraphParseError(f"line {lines[index].number}: unexpected indentation")
    if not isinstance(value, dict):
        raise GraphParseError("graph file must be a mapping at the top level")
    return value


def _require_mapping(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GraphParseError(f"{what} must be a mapping")
    return value


def _string_tuple(value: Any, what: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GraphParseError(f"{what} must be a list")
    return tuple(str(item) for item in value)


def _build_verification(value: Any, node_id: str) -> Verification | None:
    if value is None:
        return None
    block = _require_mapping(value, f"{node_id}: verification")
    raw_kind = block.get("type")
    if raw_kind is None:
        raise GraphParseError(f"{node_id}: verification requires a 'type'")
    try:
        kind = VerificationKind.parse(str(raw_kind))
    except ValueError as error:
        raise GraphParseError(f"{node_id}: {error}") from error
    commands = _string_tuple(block.get("commands"), f"{node_id}: verification.commands")
    if kind is VerificationKind.COMMANDS and not commands:
        raise GraphParseError(f"{node_id}: verification type 'commands' requires commands")
    return Verification(kind=kind, commands=commands)


def _build_node(node_id: str, value: Any) -> Node:
    block = _require_mapping(value, f"node {node_id}")
    title = block.get("title")
    if not title:
        raise GraphParseError(f"{node_id}: 'title' is required")
    raw_status = block.get("status")
    if raw_status is None:
        raise GraphParseError(f"{node_id}: 'status' is required")
    try:
        status = NodeStatus.parse(str(raw_status))
    except ValueError as error:
        raise GraphParseError(f"{node_id}: {error}") from error
    retry_budget = block.get("retry_budget")
    if retry_budget is not None and not isinstance(retry_budget, int):
        raise GraphParseError(f"{node_id}: 'retry_budget' must be an integer")
    return Node(
        id=node_id,
        title=str(title),
        depends_on=_string_tuple(block.get("depends_on"), f"{node_id}: depends_on"),
        status=status,
        worker=None if block.get("worker") is None else str(block["worker"]),
        prompt=None if block.get("prompt") is None else str(block["prompt"]),
        allowed_paths=_string_tuple(block.get("allowed_paths"), f"{node_id}: allowed_paths"),
        verification=_build_verification(block.get("verification"), node_id),
        retry_budget=retry_budget,
        note=None if block.get("note") is None else str(block["note"]),
    )


def build_graph(data: dict[str, Any]) -> Graph:
    """Turn parsed data into a validated `Graph`."""
    project = _require_mapping(data.get("project"), "'project'")
    nodes_block = data.get("nodes")
    if nodes_block is None:
        raise GraphParseError("graph file must define 'nodes'")
    nodes_map = _require_mapping(nodes_block, "'nodes'")
    if not nodes_map:
        raise GraphParseError("graph file must define at least one node")
    nodes = {node_id: _build_node(node_id, value) for node_id, value in nodes_map.items()}
    graph = Graph(
        project_id=str(project.get("id", "")),
        version=str(project.get("version", "")),
        nodes=nodes,
    )
    validate(graph)
    return graph


def load_graph_text(text: str) -> Graph:
    """Load a graph from YAML text. Used directly by tests."""
    return build_graph(parse_yaml_subset(text))


def load_graph(path: str | Path | None = None) -> Graph:
    """Load and validate the project's development graph."""
    resolved = Path(path) if path is not None else DEFAULT_GRAPH_PATH
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as error:
        raise GraphParseError(f"cannot read graph file {resolved}: {error}") from error
    return load_graph_text(text)
