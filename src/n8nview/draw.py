"""Draw a workflow in the terminal with termaid, fitted to a width."""

from __future__ import annotations

from dataclasses import dataclass, field

from termaid import render
from termaid.utils import fit_to_width, max_line_width

from .convert import Workflow, to_mermaid

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

    def themed(self, theme: str):
        """The same drawing in colour, as a rich Text. Needs termaid's rich extra."""
        from termaid import render_rich

        return render_rich(self.source, theme=theme, **self.options)


def draw(workflow: Workflow, width: int) -> Drawing:
    """Draw with node types when that fits in *width*, without them otherwise."""
    # With a type under each name a box has two rows of text and needs no
    # padding. A box with one row of text keeps it, so each edge gets its own row.
    with_types = to_mermaid(workflow, show_types=True)
    for gap, padding_x in _SPACING:
        drawing = _render(with_types, padding_y=0, gap=gap, padding_x=padding_x)
        if drawing.width <= width:
            return drawing

    without_types = to_mermaid(workflow, show_types=False)
    return fit_to_width(
        lambda **spacing: _render(without_types, padding_y=2, **spacing),
        _render(without_types, padding_y=2),
        width,
        plain=lambda drawing: drawing.text,
    )


def _render(source: str, **options: int) -> Drawing:
    options = {"inline_edge_labels": True, **options}
    return Drawing(render(source, **options), source, options)
