import io
import json
import sys
from pathlib import Path

import pytest
from termaid.utils import max_line_width

from n8nview.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
BRANCHING = str(FIXTURES / "branching.json")
LINEAR = str(FIXTURES / "linear.json")


@pytest.mark.parametrize("fixture", [LINEAR, BRANCHING])
def test_draws_within_100_columns(fixture, capsys):
    assert main(["--width", "100", fixture]) == 0
    captured = capsys.readouterr()
    assert max_line_width(captured.out.rstrip("\n")) <= 100
    assert captured.err == ""


def test_drawing_shows_names_types_branches_and_disabled(capsys):
    main(["--width", "100", BRANCHING])
    drawing = capsys.readouterr().out
    for text in ("Route by topic", "switch", "billing", "support", 'Search "docs" [v2]', "(disabled)"):
        assert text in drawing
    assert "Sticky" not in drawing
    assert "┄" in drawing


def test_drawing_starts_with_the_workflow_name_and_node_count(capsys):
    main(["--width", "100", BRANCHING])
    assert capsys.readouterr().out.startswith("Ticket triage · 10 nodes\n\n")


def test_theme_draws_the_same_workflow(capsys):
    assert main(["--width", "100", "--theme", "neon", BRANCHING]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Ticket triage · 10 nodes\n")
    assert "Route by topic" in out


def test_unknown_theme_is_a_one_line_error(capsys):
    assert main(["--theme", "nope", LINEAR]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert 'unknown theme "nope"' in captured.err
    assert captured.err.count("\n") == 1


def test_theme_without_rich_says_how_to_install_it(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "rich.console", None)
    assert main(["--theme", "neon", LINEAR]) == 1
    assert 'pip install "n8nview[color]"' in capsys.readouterr().err


def test_nodes_copied_from_the_canvas_can_be_drawn(capsys, monkeypatch):
    workflow = json.loads(Path(BRANCHING).read_text(encoding="utf-8"))
    copied = {key: workflow[key] for key in ("nodes", "connections", "pinData", "meta")}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(copied)))
    assert main(["--width", "100"]) == 0
    assert capsys.readouterr().out.startswith("10 nodes\n\n")


def test_types_are_dropped_when_the_drawing_is_too_wide(capsys):
    main(["--width", "70", LINEAR])
    assert "httpRequest" in capsys.readouterr().out
    main(["--width", "45", LINEAR])
    narrow = capsys.readouterr().out
    assert "httpRequest" not in narrow
    assert "Fetch status" in narrow


def test_mermaid_flag_prints_source_only(capsys):
    assert main(["--mermaid", LINEAR]) == 0
    out = capsys.readouterr().out
    assert "flowchart LR\n" in out
    assert "┌" not in out


def test_reads_stdin(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(Path(LINEAR).read_text(encoding="utf-8")))
    assert main(["--mermaid"]) == 0
    assert "Every morning" in capsys.readouterr().out


@pytest.mark.parametrize(
    "content, message",
    [
        ("{not json", "not valid JSON"),
        ('{"nodes": []}', "workflow has no nodes"),
        (
            '{"nodes": [{"name": "A", "type": "t"}], "connections": {"A": {"main": [[{"node": "B"}]]}}}',
            '"A" connects to a node that does not exist: "B"',
        ),
    ],
)
def test_bad_input_is_a_one_line_error(content, message, tmp_path, capsys):
    path = tmp_path / "workflow.json"
    path.write_text(content, encoding="utf-8")
    assert main([str(path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("n8nview: error: ")
    assert message in captured.err
    assert captured.err.count("\n") == 1


def test_missing_file_is_a_one_line_error(tmp_path, capsys):
    assert main([str(tmp_path / "nope.json")]) == 1
    assert capsys.readouterr().err.count("\n") == 1
