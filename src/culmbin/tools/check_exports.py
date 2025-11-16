"""A package that re-exports says what it re-exports, and both lists agree.

`units/__init__.py` imports thirty odd names and lists them in `__all__`.
Two lists of thirty names drift apart within a season, and when they do the
symptom is a name that imports from `culmbin.units.mass` and not from
`culmbin.units`, which reads as though the two were different things.

So: every name imported into a package `__init__` is in its `__all__`, every
name in `__all__` is imported, and the list is in order, because otherwise
the diff on adding one is unreadable.

The order is the one the formatter enforces, which is constants first, then
classes, then functions, each alphabetically. Sorting it any other way here
would mean this check and `ruff --fix` undoing each other's work forever.
"""

from __future__ import annotations

import ast
import sys

from culmbin.tools.sources import Module, relative, report, source_modules


def sort_key(name: str) -> tuple[int, str]:
    """The order the formatter puts `__all__` in.

    Constants first, then classes, then everything else, each alphabetically.
    """
    if name.isupper():
        return (0, name)
    if name[:1].isupper():
        return (1, name)
    return (2, name)


def _all_names(module: Module) -> list[str] | None:
    """The contents of `__all__`, or nothing if the module has none."""
    for node in module.tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                value = node.value
                if isinstance(value, ast.List | ast.Tuple):
                    return [
                        item.value
                        for item in value.elts
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    ]
    return None


def _imported(module: Module) -> set[str]:
    """Every name imported into the module from inside the package."""
    out: set[str] = set()
    for node in module.tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("culmbin"):
            out.update(alias.asname or alias.name for alias in node.names)
    return out


def _check(module: Module) -> list[str]:
    """Every problem with one package's re-exports."""
    listed = _all_names(module)
    if listed is None:
        return []
    where = relative(module.path)
    imported = _imported(module)
    problems = []
    for name in sorted(imported - set(listed)):
        problems.append(f"{where}: {name} is imported and not in __all__.")
    for name in sorted(set(listed) - imported):
        if name.startswith("__"):
            continue
        problems.append(f"{where}: {name} is in __all__ and not imported.")
    if listed != sorted(listed, key=sort_key):
        problems.append(f"{where}: __all__ is not sorted, so adding a name reads as a rewrite.")
    return problems


def problems() -> list[str]:
    """Every re-export problem in the package."""
    found = []
    for module in source_modules():
        found.extend(_check(module))
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "exports")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
