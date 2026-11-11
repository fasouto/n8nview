import json
from pathlib import Path

import pytest

from n8nview.convert import WorkflowError, parse_workflow, to_mermaid

FIXTURES = Path(__file__).parent / "fixtures"


def mermaid(name: str, **options) -> str:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return to_mermaid(parse_workflow(data), **options)


def node(name: str, type: str = "n8n-nodes-base.set", **extra) -> dict:
    return {"name": name, "type": type, "position": [0, 0], "parameters": {}, **extra}


def link(*targets: str) -> list:
    return [{"node": target, "type": "main", "index": 0} for target in targets]


def test_linear_fixture():
    assert mermaid("linear.json") == (
        "---\n"
        'title: "Daily status to Slack"\n'
        "---\n"
        "flowchart LR\n"
        '  n1["Every morning<br/>scheduleTrigger"]\n'
        '  n2["Fetch status<br/>httpRequest"]\n'
        '  n3["Post to #35;ops<br/>slack"]\n'
        "  n1 --> n2\n"
        "  n2 --> n3\n"
    )


def test_branching_fixture():
    assert mermaid("branching.json") == (
        "---\n"
        'title: "Ticket triage"\n'
        "---\n"
        "flowchart LR\n"
        '  n1["Create invoice<br/>httpRequest"]\n'
        '  n2["Reply in Slack 💬<br/>slack"]\n'
        '  n3["New ticket<br/>webhook"]\n'
        '  n4["Route by topic<br/>switch"]\n'
        '  n5["Support Agent<br/>agent"]\n'
        '  n6(["OpenAI Chat Model<br/>lmChatOpenAi"])\n'
        '  n7(["Simple Memory<br/>memoryBufferWindow"])\n'
        '  n8(["Calculator<br/>toolCalculator"])\n'
        '  n9(["Search #quot;docs#quot; [v2]<br/>toolHttpRequest"])\n'
        '  n10["Log to sheet<br/>googleSheets<br/>(disabled)"]:::disabled\n'
        "  n3 --> n4\n"
        '  n4 -->|"billing"| n1\n'
        '  n4 -->|"support"| n5\n'
        '  n4 -->|"2"| n10\n'
        "  n1 --> n2\n"
        "  n5 --> n2\n"
        "  n5 -.- n6\n"
        "  n5 -.- n7\n"
        "  n5 -.- n8\n"
        "  n5 -.- n9\n"
        "  classDef disabled color:#808080,stroke:#808080,stroke-dasharray: 4 4\n"
    )


def test_nodes_are_declared_in_canvas_order():
    top = node("Top", position=[200, 0])
    bottom = node("Bottom", position=[200, 300])
    source = to_mermaid(parse_workflow({"nodes": [bottom, top], "connections": {}}))
    assert source.index("Top") < source.index("Bottom")


def test_workflow_without_a_name_has_no_title():
    source = to_mermaid(parse_workflow({"nodes": [node("A")], "connections": {}}))
    assert source.startswith("flowchart LR\n")


def test_title_with_quotes_stays_one_quoted_string():
    source = to_mermaid(parse_workflow({"name": 'Say "hi": now', "nodes": [node("A")]}))
    assert 'title: "Say \\"hi\\": now"\n' in source


def test_sticky_notes_are_skipped():
    assert "Sticky" not in mermaid("branching.json")


def test_types_can_be_left_out():
    source = mermaid("branching.json", show_types=False)
    assert '  n3["New ticket"]\n' in source
    assert '  n10["Log to sheet<br/>(disabled)"]:::disabled\n' in source


def test_if_branches_are_labelled_true_and_false():
    workflow = parse_workflow(
        {
            "nodes": [node("Check", "n8n-nodes-base.if"), node("Yes"), node("No")],
            "connections": {"Check": {"main": [link("Yes"), link("No")]}},
        }
    )
    source = to_mermaid(workflow)
    assert '  n1 -->|"true"| n2\n' in source
    assert '  n1 -->|"false"| n3\n' in source


def test_switch_fallback_output_is_labelled():
    switch = node(
        "Route",
        "n8n-nodes-base.switch",
        parameters={"rules": {"values": [{"outputKey": "a"}]}, "options": {"fallbackOutput": "extra"}},
    )
    workflow = parse_workflow(
        {"nodes": [switch, node("A"), node("Rest")], "connections": {"Route": {"main": [link("A"), link("Rest")]}}}
    )
    assert '  n1 -->|"Fallback"| n3\n' in to_mermaid(workflow)


def test_unconnected_output_is_allowed():
    workflow = parse_workflow(
        {
            "nodes": [node("Check", "n8n-nodes-base.if"), node("No")],
            "connections": {"Check": {"main": [None, link("No")]}},
        }
    )
    assert '  n1 -->|"false"| n2\n' in to_mermaid(workflow)


def test_characters_that_break_mermaid_are_escaped():
    workflow = parse_workflow({"nodes": [node('a "b" | <c> & `d`\ne')], "connections": {}})
    assert '  n1["a #quot;b#quot; #124; #lt;c#gt; #amp; #96;d#96; e<br/>set"]\n' in to_mermaid(workflow)


@pytest.mark.parametrize(
    "data, message",
    [
        ([], "not an n8n workflow"),
        ({}, "workflow has no nodes"),
        ({"nodes": []}, "workflow has no nodes"),
        ({"nodes": [node("Note", "n8n-nodes-base.stickyNote")]}, "workflow has no nodes"),
        ({"nodes": [{"type": "n8n-nodes-base.set"}]}, 'every node needs a "name" and a "type"'),
        (
            {"nodes": [node("A")], "connections": {"A": {"main": [link("Ghost")]}}},
            '"A" connects to a node that does not exist: "Ghost"',
        ),
        (
            {"nodes": [node("A")], "connections": {"Ghost": {"main": [link("A")]}}},
            'connection from a node that does not exist: "Ghost"',
        ),
    ],
)
def test_bad_workflows_are_rejected(data, message):
    with pytest.raises(WorkflowError, match=message):
        parse_workflow(data)
