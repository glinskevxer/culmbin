"""The design note lists the layers that exist, and says something about each.

A design note is the first thing anybody reads and the last thing anybody
updates. This one is written by hand, which is right, and it is checked by a
machine, which is the only reason anybody can trust it.

Two things are checked.

**The block of layers in the note is the table in `check_layers`.** In the
same order, with nothing extra and nothing missing. A package added and not
put in the note is a package a reader will not know exists.

**Every layer has a paragraph naming it.** A line in a code block is not an
explanation, and a layer that appears in the block and nowhere else in the
note is a layer nobody has said what is for.
"""

from __future__ import annotations

import re
import sys

from culmbin.tools.check_layers import BELOW
from culmbin.tools.sources import project_root, report

DOCUMENT = "docs/design.md"
BLOCK = re.compile(r"```\n((?:\w+ +[^\n]*\n)+)```", re.MULTILINE)


def layers_in_the_note() -> list[str]:
    """Every layer the note's code block lists, in the order it lists them."""
    text = (project_root() / DOCUMENT).read_text(encoding="utf-8")
    match = BLOCK.search(text)
    if match is None:
        return []
    return [line.split()[0] for line in match.group(1).splitlines() if line.strip()]


def layers_in_the_table() -> list[str]:
    """Every layer the table holds, in the order it holds them, `errors` apart.

    `errors` is a module rather than a package and the note describes it in
    prose, so it is deliberately not in the block.
    """
    return [layer for layer in BELOW if layer not in {"", "errors"}]


def explained() -> set[str]:
    """Every layer the note says something about outside the code block."""
    text = (project_root() / DOCUMENT).read_text(encoding="utf-8")
    match = BLOCK.search(text)
    prose = text.replace(match.group(0), "") if match else text
    return {layer for layer in layers_in_the_table() if f"`{layer}`" in prose}


def problems() -> list[str]:
    """Every layer the note has lost track of."""
    path = project_root() / DOCUMENT
    if not path.exists():
        return [f"{DOCUMENT}: there is no design note."]
    note = layers_in_the_note()
    table = layers_in_the_table()
    found = []
    for layer in sorted(set(table) - set(note)):
        found.append(f"{DOCUMENT}: {layer} is a package and the note does not list it.")
    for layer in sorted(set(note) - set(table)):
        found.append(f"{DOCUMENT}: the note lists {layer}, which is not a package.")
    if not found and note != table:
        found.append(f"{DOCUMENT}: the note lists the layers in a different order from the table.")
    for layer in sorted(set(table) - explained()):
        found.append(f"{DOCUMENT}: {layer} is listed and nothing says what it is for.")
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "design")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
