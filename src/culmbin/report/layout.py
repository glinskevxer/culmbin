"""Fixed width layout, which knows nothing about malt.

Everything in this module is text in and text out. There is no malt in it,
no book, and no clock, which is what makes the pages above it testable: a
report is then a function from records to rows, and the rows are laid out by
something that has already been proved to lay rows out.

The width is 96 characters throughout. That is what the intake office
printer fits and it has not changed since the printer was bought.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum, unique

PAGE_WIDTH = 96
GAP = "  "


@unique
class Align(StrEnum):
    """Which way a column's contents are pushed."""

    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class Column:
    """One column of a table.

    A width of `None` means as wide as the widest thing in it, heading
    included, which is what nearly every column wants.
    """

    heading: str
    align: Align = Align.LEFT
    width: int | None = None

    def sized(self, cells: Sequence[str]) -> int:
        """How wide this column ends up."""
        if self.width is not None:
            return self.width
        return (
            max(len(self.heading), *(len(cell) for cell in cells)) if cells else len(self.heading)
        )


def fit(text: str, width: int, align: Align = Align.LEFT) -> str:
    """Pad or cut a cell to a width.

    Cutting is a last resort and it leaves a full stop, so that a truncated
    name is obvious rather than merely wrong.
    """
    if width <= 0:
        return ""
    if len(text) > width:
        return text[: width - 1] + "." if width > 1 else text[:width]
    return text.rjust(width) if align is Align.RIGHT else text.ljust(width)


def rule(width: int = PAGE_WIDTH, char: str = "-") -> str:
    """A horizontal rule."""
    if not char:
        raise ValueError("a rule needs something to draw with")
    return (char * width)[:width]


def wrap(text: str, width: int) -> list[str]:
    """Break text on spaces to a width.

    A word longer than the width goes on a line of its own and overhangs,
    because breaking a lot code in half is worse than a ragged margin.
    """
    if width <= 0:
        raise ValueError(f"cannot wrap to {width} characters")
    lines: list[str] = []
    current = ""
    for word in text.split():
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def table(columns: Sequence[Column], rows: Sequence[Sequence[str]]) -> list[str]:
    """Lay out a table: heading, rule, rows.

    Every row has to have as many cells as there are columns. A short row is
    a bug in the caller and filling it in quietly is how a column ends up
    one to the left for a whole page.
    """
    if not columns:
        raise ValueError("a table needs columns")
    for index, row in enumerate(rows):
        if len(row) != len(columns):
            raise ValueError(
                f"row {index} has {len(row)} cells and the table has {len(columns)} columns"
            )
    widths = [column.sized([row[index] for row in rows]) for index, column in enumerate(columns)]
    lines = [
        GAP.join(
            fit(column.heading, widths[index], column.align) for index, column in enumerate(columns)
        ).rstrip()
    ]
    lines.append(rule(sum(widths) + len(GAP) * (len(widths) - 1)))
    for row in rows:
        lines.append(
            GAP.join(
                fit(cell, widths[index], columns[index].align) for index, cell in enumerate(row)
            ).rstrip()
        )
    return lines


def pairs(items: Sequence[tuple[str, str]], gap: int = 2) -> list[str]:
    """A block of label and value, with the labels lined up."""
    if not items:
        return []
    width = max(len(label) for label, _ in items)
    return [f"{label.ljust(width)}{' ' * gap}{value}" for label, value in items]


def heading(text: str, width: int = PAGE_WIDTH) -> list[str]:
    """A page or section heading with a rule under it."""
    return [text, rule(min(width, max(len(text), 1)), "=")]


def block(title: str, lines: Sequence[str]) -> list[str]:
    """A titled block, or nothing at all if there is nothing in it.

    Returning nothing for an empty block is deliberate. A page with six
    empty headings on it is a page nobody reads to the bottom of.
    """
    if not lines:
        return []
    return [title, *lines]


def table_block(title: str, columns: Sequence[Column], rows: Sequence[Sequence[str]]) -> list[str]:
    """A titled table, or nothing at all if there are no rows.

    `block` cannot do this on its own, because a table with no rows still
    has a heading and a rule in it, so it never looks empty. That is exactly
    how a page ends up with six headings and nothing under any of them.
    """
    if not rows:
        return []
    return block(title, table(columns, rows))


def page(sections: Iterable[Sequence[str]]) -> str:
    """Join sections with a blank line between them, ending in a newline."""
    blocks = [list(section) for section in sections if section]
    body = "\n\n".join("\n".join(lines) for lines in blocks)
    return f"{body}\n" if body else ""


def money(amount: object, width: int = 10) -> str:
    """A money value, right aligned in a column of its own width."""
    return fit(str(amount), width, Align.RIGHT)


def number(value: float, places: int = 2, width: int = 8) -> str:
    """A number, right aligned to a fixed number of places."""
    return fit(f"{value:.{places}f}", width, Align.RIGHT)
