"""Draw a workflow in the terminal with termaid, fitted to a width."""

from __future__ import annotations

from dataclasses import dataclass, field

from termaid import render
from termaid.utils import fit_to_width, max_line_width

from .convert import Mark, Workflow, to_mermaid

# (gap, padding_x) from roomy to tight, the same steps termaid's own CLI takes.
_SPACING = ((4, 4), (2, 4), (1, 4), (1, 2))


@dataclass(frozen=True)
class Drawing:
    text: str
    source: str
    options: dict = field(default_factory=dict)

    @property
    def width(self) -> int:
        return max_line_width(self.text)

    def styled_lines(self) -> list[list[dict]]:
        """The same drawing as lines of {"text", "style"} chunks, for a tool that picks the colours."""
        from termaid import render_styled

        lines = []
        for line in render_styled(self.source, **self.options)["lines"]:
            merged: list[dict] = []
            for chunk in line:
                if merged and merged[-1]["style"] == chunk["style"]:
                    merged[-1]["text"] += chunk["text"]
                else:
                    merged.append({"text": chunk["text"], "style": chunk["style"]})
            lines.append(merged)
        return lines

    def themed(self, theme: str):
        """The same drawing in colour, as a rich Text. Needs termaid's rich extra."""
        from termaid import render_rich

        return render_rich(self.source, theme=theme, **self.options)


def draw(workflow: Workflow, width: int, marks: dict[str, Mark] | None = None) -> Drawing:
    """Draw with node types when that fits in *width*, without them otherwise."""
    # With a type under each name a box has two rows of text and needs no
    # padding. A box with one row of text keeps it, so each edge gets its own row.
    with_types = to_mermaid(workflow, show_types=True, marks=marks)
    for gap, padding_x in _SPACING:
        drawing = _render(with_types, padding_y=0, gap=gap, padding_x=padding_x)
        if drawing.width <= width:
            return drawing

    without_types = to_mermaid(workflow, show_types=False, marks=marks)
    padding_y = 0 if marks else 2
    return fit_to_width(
        lambda **spacing: _render(without_types, padding_y=padding_y, **spacing),
        _render(without_types, padding_y=padding_y),
        width,
        plain=lambda drawing: drawing.text,
    )


def _render(source: str, **options: int) -> Drawing:
    options = {"inline_edge_labels": True, **options}
    return Drawing(render(source, **options), source, options)
