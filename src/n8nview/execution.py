"""Read the workflow that one n8n execution ran and how far each node got."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .convert import MAIN, Mark, Workflow, parse_workflow

_LIVE = {"new", "running", "waiting"}
_ERROR_WIDTH = 28


@dataclass(frozen=True)
class Execution:
    id: str
    status: str
    workflow: Workflow
    marks: dict[str, Mark]
    seconds: float | None

    @property
    def is_live(self) -> bool:
        return self.status in _LIVE

    @property
    def title(self) -> str:
        state = self.status if self.seconds is None else f"{self.status} in {_duration(self.seconds * 1000)}"
        return f"{self.workflow.title} · execution {self.id} · {state}"


def is_execution(data: object) -> bool:
    return isinstance(data, dict) and "workflowData" in data


def parse_execution(data: dict) -> Execution:
    """Parse what `GET /executions/{id}?includeData=true` returns."""
    workflow_data = data.get("workflowData")
    workflow = parse_workflow(workflow_data)
    status = str(data.get("status") or "unknown")
    run_data = _run_data(data)
    ids = {node.name: node.id for node in workflow.nodes}
    live = status in _LIVE

    marks: dict[str, Mark] = {}
    for node in workflow.nodes:
        runs = run_data.get(node.name)
        if runs:
            marks[node.id] = _finished_mark(runs)
        elif not node.disabled:
            marks[node.id] = Mark("○ pending", "idle") if live else Mark("– not run", "idle")
    if live:
        for name in _running_nodes(workflow_data.get("connections") or {}, run_data):
            if name in ids:
                marks[ids[name]] = Mark("▶ running", "running")

    return Execution(str(data.get("id", "?")), status, workflow, marks, _seconds(data))


def _run_data(data: dict) -> dict[str, list[dict]]:
    """Runs per node name. Empty while n8n has saved nothing for this execution yet."""
    result = (data.get("data") or {}).get("resultData") or {}
    run_data = result.get("runData")
    return run_data if isinstance(run_data, dict) else {}


def _finished_mark(runs: list[dict]) -> Mark:
    last = runs[-1]
    times = f" ×{len(runs)}" if len(runs) > 1 else ""
    if last.get("executionStatus") == "error" or last.get("error"):
        message = " ".join(str((last.get("error") or {}).get("message") or "failed").split())
        if len(message) > _ERROR_WIDTH:
            message = message[: _ERROR_WIDTH - 1] + "…"
        return Mark(f"× {message}{times}", "failed")
    return Mark(f"● {_duration(last.get('executionTime') or 0)}{times}", "ok")


def _running_nodes(connections: dict, run_data: dict[str, list[dict]]) -> set[str]:
    """Nodes that received items from a finished node and have not finished themselves.

    n8n saves a node's result when the node ends, so a node that is running
    shows up only as the target of an output that already carries items.
    """
    running: set[str] = set()
    for source, runs in run_data.items():
        outputs = ((runs[-1].get("data") or {}).get(MAIN)) or []
        wired = (connections.get(source) or {}).get(MAIN) or []
        for items, targets in zip(outputs, wired):
            if not items:
                continue
            for target in targets or []:
                name = target.get("node") if isinstance(target, dict) else None
                if name and name not in run_data:
                    running.add(name)
    return running


def _seconds(data: dict) -> float | None:
    try:
        started = datetime.fromisoformat(str(data["startedAt"]).replace("Z", "+00:00"))
        stopped = datetime.fromisoformat(str(data["stoppedAt"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None
    return (stopped - started).total_seconds()


def _duration(milliseconds: float) -> str:
    if milliseconds < 1000:
        return f"{round(milliseconds)}ms"
    return f"{milliseconds / 1000:.1f}s"

