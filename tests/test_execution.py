import json
from pathlib import Path

import pytest

from n8nview.api import N8nApi
from n8nview.cli import main
from n8nview.execution import parse_execution

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"execution-{name}.json").read_text(encoding="utf-8"))


def marks(name: str) -> dict:
    execution = parse_execution(load(name))
    names = {node.id: node.name for node in execution.workflow.nodes}
    return {names[node_id]: mark.text for node_id, mark in execution.marks.items()}


def test_running_execution_marks_done_running_and_pending_nodes():
    assert marks("running") == {
        "New order": "● 0ms",
        "Check stock": "● 3.0s",
        "Should fail?": "● 6ms",
        "Charge card": "▶ running",
        "Crash": "○ pending",
        "Ship": "○ pending",
        "Send receipt": "○ pending",
    }


def test_finished_execution_marks_the_branch_that_did_not_run():
    result = marks("success")
    assert result["Send receipt"].startswith("● ")
    assert result["Crash"] == "– not run"


def test_failed_execution_shows_the_error_on_the_node_that_failed():
    result = marks("error")
    assert result["Crash"] == "× Card declined"
    assert result["Charge card"] == "– not run"


@pytest.mark.parametrize(
    "name, state",
    [("running", "running"), ("success", "success in 9.0s"), ("error", "error in 3.1s")],
)
def test_title_names_the_execution_and_its_state(name, state):
    execution = parse_execution(load(name))
    assert execution.title == f"Order pipeline · 7 nodes · execution {execution.id} · {state}"


def test_running_execution_without_saved_progress_marks_every_node_pending():
    data = load("running")
    data["data"]["resultData"]["runData"] = {}
    assert set(marks_of(data).values()) == {"○ pending"}


def marks_of(data: dict) -> dict:
    execution = parse_execution(data)
    return {node_id: mark.text for node_id, mark in execution.marks.items()}


def test_a_node_that_ran_several_times_shows_the_count():
    data = load("success")
    runs = data["data"]["resultData"]["runData"]["Ship"]
    runs.append(runs[0])
    execution = parse_execution(data)
    ship = next(node.id for node in execution.workflow.nodes if node.name == "Ship")
    assert execution.marks[ship].text.endswith(" ×2")


def test_cli_draws_an_execution_file(capsys):
    assert main(["--width", "110", str(FIXTURES / "execution-error.json")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Order pipeline · 7 nodes · execution ")
    assert "× Card declined" in out


def test_cli_prints_execution_marks_as_mermaid(capsys):
    assert main(["--mermaid", str(FIXTURES / "execution-running.json")]) == 0
    out = capsys.readouterr().out
    assert "<br/>▶ running" in out
    assert "classDef running " in out


def test_styled_json_tags_each_node_with_its_state(capsys):
    assert main(["--format", "styled-json", "--width", "110", str(FIXTURES / "execution-running.json")]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["title"].endswith("· running")
    styles = {chunk["text"]: chunk["style"] for line in document["lines"] for chunk in line}
    assert styles["Check stock"] == "class:ok:text"
    assert styles["▶ running"] == "class:running:text"
    assert styles["○ pending"] == "class:idle:text"
    plain = "\n".join("".join(chunk["text"] for chunk in line) for line in document["lines"])
    main(["--width", "110", str(FIXTURES / "execution-running.json")])
    assert capsys.readouterr().out.endswith(plain + "\n")


class FakeN8n:
    """Answers like the n8n API: running executions are listed only when asked for."""

    def __init__(self, executions: list[dict]):
        self.executions = executions
        self.paths: list[str] = []

    def get(self, path, **query):
        self.paths.append(path)
        if path == "/executions":
            wanted = query.get("status")
            found = [e for e in self.executions if (e["status"] == wanted if wanted else e["status"] != "running")]
            return {"data": [{"id": e["id"], "status": e["status"]} for e in found[:1]]}
        return next(e for e in self.executions if path == f"/executions/{e['id']}")


@pytest.fixture
def n8n(monkeypatch):
    def install(*names: str) -> FakeN8n:
        fake = FakeN8n([load(name) for name in names])
        monkeypatch.setattr(N8nApi, "_get", fake.get)
        monkeypatch.setenv("N8N_API_KEY", "test-key")
        return fake

    return install


def test_latest_prefers_the_running_execution(n8n, capsys):
    n8n("error", "running")
    assert main(["--latest", "--width", "110"]) == 0
    assert "▶ running" in capsys.readouterr().out


def test_latest_falls_back_to_the_last_finished_execution(n8n, capsys):
    n8n("error")
    assert main(["--latest", "--width", "110"]) == 0
    assert "× Card declined" in capsys.readouterr().out


def test_latest_without_executions_is_a_one_line_error(n8n, capsys):
    n8n()
    assert main(["--latest"]) == 1
    assert capsys.readouterr().err == "n8nview: error: n8n has no executions to show yet\n"


def test_latest_without_an_api_key_says_how_to_set_one(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(["--latest"]) == 1
    assert "set N8N_API_KEY" in capsys.readouterr().err


def test_api_settings_can_come_from_a_dotenv_file(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    monkeypatch.delenv("N8N_BASE_URL", raising=False)
    (tmp_path / ".env").write_text('# local n8n\nN8N_BASE_URL=http://127.0.0.1:9\nexport N8N_API_KEY="from-file"\n')
    monkeypatch.chdir(tmp_path)
    assert main(["--latest"]) == 1
    assert "cannot reach n8n at http://127.0.0.1:9" in capsys.readouterr().err


def test_unreachable_n8n_is_a_one_line_error(monkeypatch, capsys):
    monkeypatch.setenv("N8N_API_KEY", "test-key")
    assert main(["--latest", "--url", "http://127.0.0.1:9"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("n8nview: error: cannot reach n8n at http://127.0.0.1:9")
    assert err.count("\n") == 1


def test_watch_redraws_only_when_the_execution_changes(n8n, monkeypatch, capsys):
    fake = n8n("running")
    ticks = []

    def sleep(seconds):
        ticks.append(seconds)
        if len(ticks) == 2:
            fake.executions[:] = [load("success")]
        if len(ticks) == 4:
            raise KeyboardInterrupt

    monkeypatch.setattr("time.sleep", sleep)
    assert main(["--latest", "--watch", "--width", "110"]) == 0
    out = capsys.readouterr().out
    assert out.count("Order pipeline · 7 nodes") == 2
    assert out.index("▶ running") < out.index("success in 9.0s")


def test_watch_needs_latest(capsys):
    assert main(["--watch"]) == 1
    assert "--watch needs --latest" in capsys.readouterr().err

