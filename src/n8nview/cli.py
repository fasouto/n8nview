"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import shutil
import sys

from . import __version__
from .convert import Workflow, WorkflowError, parse_workflow, to_mermaid
from .draw import Drawing, draw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="n8nview",
        description="Draw an n8n workflow export in the terminal.",
    )
    parser.add_argument("file", nargs="?", help="workflow JSON exported from n8n (reads stdin if omitted)")
    parser.add_argument("--mermaid", action="store_true", help="print the Mermaid source instead of drawing")
    parser.add_argument("--width", type=int, help="maximum width in columns (default: the terminal width)")
    parser.add_argument("--theme", help="draw in colour with a termaid theme, such as neon or nord")
    parser.add_argument("--version", action="version", version=f"n8nview {__version__}")
    args = parser.parse_args(argv)

    try:
        workflow = parse_workflow(_read_json(args.file))
        if args.mermaid:
            sys.stdout.write(to_mermaid(workflow))
            return 0
        width = args.width or shutil.get_terminal_size(fallback=(100, 24)).columns
        drawing = draw(workflow, width)
        if args.theme:
            _print_themed(workflow, drawing, args.theme)
        else:
            print(f"{workflow.title}\n\n{drawing.text}")
    except WorkflowError as error:
        print(f"n8nview: error: {error}", file=sys.stderr)
        return 1

    if drawing.width > width:
        print(f"n8nview: drawing is {drawing.width} columns wide, wider than {width}", file=sys.stderr)
    return 0


def _print_themed(workflow: Workflow, drawing: Drawing, theme: str) -> None:
    try:
        from rich.console import Console
        from termaid.renderer.themes import THEMES
    except ImportError as error:
        raise WorkflowError('--theme needs the colour extra: pip install "n8nview[color]"') from error
    if theme not in THEMES:
        raise WorkflowError(f'unknown theme "{theme}" (choose from: {", ".join(THEMES)})')

    # A console narrower than the drawing would wrap its lines.
    console = Console(width=max(drawing.width, len(workflow.title)), highlight=False)
    console.print(workflow.title, style="bold", markup=False)
    console.print()
    console.print(drawing.themed(theme))


def _read_json(path: str | None) -> object:
    try:
        if path is None:
            if sys.stdin.isatty():
                raise WorkflowError("no input (pass a workflow file or pipe one to stdin)")
            text = sys.stdin.read()
        else:
            with open(path, encoding="utf-8-sig") as file:
                text = file.read()
    except (OSError, UnicodeDecodeError) as error:
        raise WorkflowError(f"cannot read {path or 'stdin'}: {error}") from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise WorkflowError(f"not valid JSON: {error}") from error
