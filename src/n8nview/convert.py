"""Convert an n8n workflow export to Mermaid flowchart source."""

from __future__ import annotations

import json
from dataclasses import dataclass

STICKY_NOTE = "n8n-nodes-base.stickyNote"
MAIN = "main"

_ENTITIES = {
    "&": "#amp;",
    '"': "#quot;",
    "<": "#lt;",
    ">": "#gt;",
    "#": "#35;",
    "`": "#96;",
    "|": "#124;",
    "\n": " ",
    "\r": " ",
}


class WorkflowError(ValueError):
    """The input is not a workflow that can be drawn."""


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    type: str
    disabled: bool
    parameters: dict

    @property
    def short_type(self) -> str:
        return self.type.rsplit(".", 1)[-1]


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str
    label: str | None = None


@dataclass(frozen=True)
class Workflow:
    nodes: list[Node]
    edges: list[Edge]
    name: str | None = None

    @property
    def title(self) -> str:
        count = f"{len(self.nodes)} node{'' if len(self.nodes) == 1 else 's'}"
        return f"{self.name} · {count}" if self.name else count

    @property
    def sub_node_ids(self) -> set[str]:
        """Nodes that attach to another node (model, memory, tool) instead of running in the flow."""
        return {edge.source for edge in self.edges if edge.kind != MAIN}


def parse_workflow(data: object) -> Workflow:
    if not isinstance(data, dict):
        raise WorkflowError("not an n8n workflow (expected a JSON object)")
    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise WorkflowError("workflow has no nodes")

    for raw in raw_nodes:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str) or not isinstance(raw.get("type"), str):
            raise WorkflowError('every node needs a "name" and a "type"')

    nodes: dict[str, Node] = {}
    for raw in _in_canvas_order(raw_nodes):
        if raw["type"] == STICKY_NOTE:
            continue
        parameters = raw.get("parameters")
        nodes[raw["name"]] = Node(
            id=f"n{len(nodes) + 1}",
            name=raw["name"],
            type=raw["type"],
            disabled=raw.get("disabled") is True,
            parameters=parameters if isinstance(parameters, dict) else {},
        )
    if not nodes:
        raise WorkflowError("workflow has no nodes")

    connections = data.get("connections", {})
    if not isinstance(connections, dict):
        raise WorkflowError('"connections" must be an object')

    edges: list[Edge] = []
    for source_name, by_kind in connections.items():
        source = nodes.get(source_name)
        if source is None:
            raise WorkflowError(f'connection from a node that does not exist: "{source_name}"')
        if not isinstance(by_kind, dict):
            raise WorkflowError(f'connections of "{source_name}" must be an object')
        for kind, outputs in by_kind.items():
            if not isinstance(outputs, list):
                raise WorkflowError(f'"{kind}" connections of "{source_name}" must be a list')
            for index, targets in enumerate(outputs):
                for target in targets or []:
                    target_name = target.get("node") if isinstance(target, dict) else None
                    if target_name not in nodes:
                        raise WorkflowError(
                            f'"{source_name}" connects to a node that does not exist: "{target_name}"'
                        )
                    label = _branch_label(source, index) if kind == MAIN else None
                    edges.append(Edge(source.id, nodes[target_name].id, kind, label))

    # Main edges first: termaid lays out the flow in the order edges appear.
    edges.sort(key=lambda edge: edge.kind != MAIN)
    name = data.get("name")
    return Workflow(list(nodes.values()), edges, name.strip() if isinstance(name, str) and name.strip() else None)


def _in_canvas_order(raw_nodes: list[dict]) -> list[dict]:
    """Top to bottom, then left to right, so branches stack the way they do in the n8n editor."""
    def is_point(position: object) -> bool:
        return (
            isinstance(position, list)
            and len(position) == 2
            and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in position)
        )

    if not all(is_point(raw.get("position")) for raw in raw_nodes):
        return raw_nodes
    return sorted(raw_nodes, key=lambda raw: (raw["position"][1], raw["position"][0]))


def _branch_label(node: Node, output: int) -> str | None:
    """Name of one output of an IF or Switch node, as the n8n editor shows it."""
    if node.type == "n8n-nodes-base.if":
        return ("true", "false")[output] if output < 2 else str(output)
    if node.type == "n8n-nodes-base.switch":
        rules = node.parameters.get("rules")
        values = rules.get("values") if isinstance(rules, dict) else None
        values = values if isinstance(values, list) else []
        if output < len(values):
            rule = values[output]
            key = rule.get("outputKey") if isinstance(rule, dict) else None
            return str(key) if key else str(output)
        options = node.parameters.get("options")
        if output == len(values) and isinstance(options, dict) and options.get("fallbackOutput") == "extra":
            return str(options.get("renameFallbackOutput") or "Fallback")
        return str(output)
    return None


def _escape(text: str) -> str:
    return "".join(_ENTITIES.get(char, char) for char in text)


def to_mermaid(workflow: Workflow, *, show_types: bool = True) -> str:
    sub_nodes = workflow.sub_node_ids
    lines = ["flowchart LR"]
    if workflow.name:
        # A JSON string is also a YAML double-quoted string.
        lines = ["---", f"title: {json.dumps(workflow.name, ensure_ascii=False)}", "---", *lines]
    for node in workflow.nodes:
        parts = [node.name]
        if show_types:
            parts.append(node.short_type)
        if node.disabled:
            parts.append("(disabled)")
        label = "<br/>".join(_escape(part) for part in parts)
        opening, closing = ('(["', '"])') if node.id in sub_nodes else ('["', '"]')
        suffix = ":::disabled" if node.disabled else ""
        lines.append(f"  {node.id}{opening}{label}{closing}{suffix}")
    for edge in workflow.edges:
        if edge.kind != MAIN:
            # n8n stores a sub-node as the source. Drawn from the agent's side it
            # sits next to the agent, not in the first column with the triggers.
            lines.append(f"  {edge.target} -.- {edge.source}")
        elif edge.label is not None:
            lines.append(f'  {edge.source} -->|"{_escape(edge.label)}"| {edge.target}')
        else:
            lines.append(f"  {edge.source} --> {edge.target}")
    if any(node.disabled for node in workflow.nodes):
        lines.append("  classDef disabled color:#808080,stroke:#808080,stroke-dasharray: 4 4")
    return "\n".join(lines) + "\n"
