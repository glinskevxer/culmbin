"""One module asks what day it is, and everything else is told.

The clock enters the package in `cli/main.py` and nowhere else. Every rule
below that takes the day as an argument, which is what makes a report for
last Tuesday the same code as a report for today, and what makes every one
of those rules testable without freezing time.

This check reads for the calls rather than for the imports, because
`datetime` is imported all over the package and quite properly: a date is a
value and the ban is on asking for the current one.
"""

from __future__ import annotations

import ast
import sys

from culmbin.tools.sources import relative, report, source_modules

ALLOWED = frozenset({"culmbin.cli.main"})
"""The one module that may ask what day it is."""

CLOCK_CALLS = frozenset({"today", "now", "utcnow", "time", "monotonic", "fromtimestamp"})
"""Calls that reach for the current moment rather than take one."""


def _clock_call(node: ast.Call) -> str | None:
    """The name of the clock call, if this is one."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in CLOCK_CALLS:
        return func.attr
    if isinstance(func, ast.Name) and func.id in CLOCK_CALLS:
        return func.id
    return None


def problems() -> list[str]:
    """Every module below the console script that reads a clock."""
    found = []
    for module in source_modules():
        if module.dotted in ALLOWED:
            continue
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Call):
                continue
            call = _clock_call(node)
            if call is not None:
                found.append(
                    f"{relative(module.path)}:{node.lineno}: calls {call}(), "
                    f"and the day is an argument everywhere but {sorted(ALLOWED)[0]}."
                )
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "clock")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
