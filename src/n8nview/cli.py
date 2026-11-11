"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

from . import __version__
from .api import N8nApi
from .convert import Mark, Workflow, WorkflowError, parse_workflow, to_mermaid
from .draw import Drawing, draw
from .execution import is_execution, parse_execution

_CLEAR_SCREEN = "\x1b[H\x1b[2J\x1b[3J"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="n8nview",
        description="Draw an n8n workflow, or one of its executions, in the terminal.",
    )
    parser.add_argument("file", nargs="?", help="workflow or execution JSON from n8n (reads stdin if omitted)")
    parser.add_argument("--mermaid", action="store_true", help="print the Mermaid source instead of drawing")
    parser.add_argument("--width", type=int, help="maximum width in columns (default: the terminal width)")
    parser.add_argument("--theme", help="draw in colour with a termaid theme, such as neon or nord")
    parser.add_argument(
        "--format",
        choices=["text", "styled-json"],
        default="text",
        help="styled-json prints the drawing as JSON chunks tagged with a style, for editors and plugins",
    )
    live = parser.add_argument_group("executions, read from the n8n API with N8N_API_KEY")
    live.add_argument("--latest", action="store_true", help="draw the execution that is running, or else the last one")
    live.add_argument("--watch", action="store_true", help="with --latest, keep redrawing as the execution advances")
    live.add_argument("--workflow", metavar="ID", help="with --latest, only look at this workflow's executions")
    live.add_argument("--url", help="where n8n is (default: N8N_BASE_URL, or http://localhost:5678)")
    live.add_argument("--interval", type=float, default=1.0, help="seconds between checks with --watch (default: 1)")
    parser.add_argument("--version", action="version", version=f"n8nview {__version__}")
    args = parser.parse_args(argv)

    try:
        if args.watch and not args.latest:
            raise WorkflowError("--watch needs --latest")
        if args.latest and args.file:
            raise WorkflowError("--latest reads from the n8n API, so it takes no file")
        if args.watch:
            return _watch(args)
        data = _api(args).latest_execution(args.workflow) if args.latest else _read_json(args.file)
        frame, too_wide = _frame(data, args)
    except WorkflowError as error:
        print(f"n8nview: error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    sys.stdout.write(frame)
    if too_wide:
        print(f"n8nview: {too_wide}", file=sys.stderr)
    return 0


def _frame(data: object, args: argparse.Namespace) -> tuple[str, str | None]:
    """The text to print for one workflow or execution, and a note when it is too wide."""
    marks: dict[str, Mark] | None = None
    if is_execution(data):
        execution = parse_execution(data)
        workflow, title, marks = execution.workflow, execution.title, execution.marks
    else:
        workflow = parse_workflow(data)
        title = workflow.title
    if args.mermaid:
        return to_mermaid(workflow, marks=marks), None

    width = args.width or shutil.get_terminal_size(fallback=(100, 24)).columns
    drawing = draw(workflow, width, marks)
    if args.format == "styled-json":
        document = {"version": 1, "title": title, "lines": drawing.styled_lines()}
        text = json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"
    elif args.theme:
        text = _themed(title, drawing, args.theme)
    else:
        text = f"{title}\n\n{drawing.text}\n"
    too_wide = f"drawing is {drawing.width} columns wide, wider than {width}" if drawing.width > width else None
    return text, too_wide


def _watch(args: argparse.Namespace) -> int:
    """Redraw the latest execution each time it changes, until interrupted."""
    api = _api(args)
    clear = _CLEAR_SCREEN if sys.stdout.isatty() else ""
    shown = None
    try:
        while True:
            try:
                frame, _ = _frame(api.latest_execution(args.workflow), args)
            except WorkflowError as error:
                frame = f"n8nview: {error}\n"
            if frame != shown:
                sys.stdout.write(clear + frame + ("" if clear else "\n"))
                sys.stdout.flush()
                shown = frame
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def _api(args: argparse.Namespace) -> N8nApi:
    settings = {**_dotenv(".env"), **os.environ}
    key = settings.get("N8N_API_KEY")
    if not key:
        raise WorkflowError("set N8N_API_KEY to an n8n API key, in the environment or in .env")
    return N8nApi(args.url or settings.get("N8N_BASE_URL") or "http://localhost:5678", key)


def _dotenv(path: str) -> dict[str, str]:
    """KEY=value lines of a .env file in the current directory, if there is one."""
    try:
        with open(path, encoding="utf-8") as file:
            lines = file.read().splitlines()
    except OSError:
        return {}
    settings = {}
    for line in lines:
        key, separator, value = line.strip().partition("=")
        if separator and key and not key.startswith("#"):
            settings[key.removeprefix("export ").strip()] = value.strip().strip("\"'")
    return settings


def _themed(title: str, drawing: Drawing, theme: str) -> str:
    try:
        from rich.console import Console
        from termaid.renderer.themes import THEMES
    except ImportError as error:
        raise WorkflowError('--theme needs the colour extra: pip install "n8nview[color]"') from error
    if theme not in THEMES:
        raise WorkflowError(f'unknown theme "{theme}" (choose from: {", ".join(THEMES)})')

    # A console narrower than the drawing would wrap its lines.
    console = Console(width=max(drawing.width, len(title)), highlight=False)
    with console.capture() as capture:
        console.print(title, style="bold", markup=False)
        console.print()
        console.print(drawing.themed(theme))
    return capture.get()


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
