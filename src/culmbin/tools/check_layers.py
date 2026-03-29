"""The layering is a table, and it is checked rather than described.

A layer may import from the layers below it and from nothing else. The table
below is the whole rule. It is here rather than in a design document because
a design document does not fail a build.

The two lines worth explaining:

`units` imports from nothing in the package except `errors`, which is why it
can be read on its own and why every conversion in it is a function of its
arguments.

`cli` may import from everything, and nothing may import from `cli`. That is
what makes the clock enter the package in exactly one place.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping

from culmbin.tools.sources import PACKAGE, relative, report, source_modules

BELOW: Mapping[str, frozenset[str]] = {
    "": frozenset(),
    "errors": frozenset(),
    "units": frozenset({"errors"}),
    "model": frozenset({"errors", "units"}),
    "store": frozenset({"errors", "units", "model", "intake", "process"}),
    "intake": frozenset({"errors", "units", "model", "store"}),
    "process": frozenset({"errors", "units", "model", "store"}),
    "blend": frozenset({"errors", "units", "model", "store"}),
    "sales": frozenset({"errors", "units", "model", "store", "process", "report"}),
    "trace": frozenset({"errors", "units", "model", "store"}),
    "report": frozenset(
        {"errors", "units", "model", "store", "intake", "process", "blend", "sales", "trace"}
    ),
    "cli": frozenset(
        {
            "errors",
            "units",
            "model",
            "store",
            "intake",
            "process",
            "blend",
            "sales",
            "trace",
            "report",
        }
    ),
    "tools": frozenset(
        {
            "errors",
            "units",
            "model",
            "store",
            "intake",
            "process",
            "blend",
            "sales",
            "trace",
            "report",
            "cli",
        }
    ),
}
"""What each layer is allowed to import from.

The empty key is the package's own `__init__`, which holds the version and
imports nothing.

`store` may reach up into `intake` and `process` for the records they own,
which is the one place the layering bends: an intake standard and a steep
programme are values that belong to those packages and are written down by
this one.
"""


def layers() -> tuple[str, ...]:
    """Every layer, in the order they are allowed to depend."""
    return tuple(BELOW)


def problems() -> list[str]:
    """Every import that crosses the layering the wrong way."""
    found = []
    for module in source_modules():
        layer = module.layer
        if layer not in BELOW:
            found.append(f"{relative(module.path)}: {layer!r} is not a layer in the table.")
            continue
        allowed = BELOW[layer] | {layer}
        for imported in module.imports():
            if not imported.startswith(f"{PACKAGE}."):
                continue
            other = imported.split(".")[1]
            if other not in allowed:
                found.append(
                    f"{relative(module.path)}: {layer} imports from {other}, which is not below it."
                )
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "layers")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
