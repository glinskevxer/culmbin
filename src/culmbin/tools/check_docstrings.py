"""Every module and every public definition has a docstring, and it says why.

The rule is not that a docstring exists. It is that a docstring exists and
is not a restatement of the name, because `def malting_loss(): "Malting
loss."` is worse than nothing: it takes up the space where the reason would
have gone and makes the file look documented.

So a docstring whose first line is the function's own name with the
underscores taken out is a problem here.
"""

from __future__ import annotations

import ast
import sys

from culmbin.tools.sources import Module, public, relative, report, source_modules

MINIMUM_WORDS = 3


def _restates(name: str, first_line: str) -> bool:
    """Whether a first line is the name back again with spaces in it."""
    plain = first_line.rstrip(".").lower()
    return plain == name.replace("_", " ").lower()


def _check_module(module: Module) -> list[str]:
    """Every problem in one module."""
    problems = []
    where = relative(module.path)
    if module.docstring is None:
        problems.append(f"{where}: the module has no docstring.")
    for node in module.definitions():
        if not public(node.name):
            continue
        text = ast.get_docstring(node)
        if text is None:
            problems.append(f"{where}:{node.lineno}: {node.name} has no docstring.")
            continue
        first = text.strip().splitlines()[0]
        if len(first.split()) < MINIMUM_WORDS:
            problems.append(
                f"{where}:{node.lineno}: {node.name} has a docstring of {len(first.split())} words."
            )
        elif _restates(node.name, first):
            problems.append(f"{where}:{node.lineno}: {node.name} says its own name back again.")
    return problems


def problems() -> list[str]:
    """Every docstring problem in the package."""
    found = []
    for module in source_modules():
        found.extend(_check_module(module))
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "docstrings")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
