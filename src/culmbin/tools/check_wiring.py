"""A public name nothing refers to is dead, and its own module does not count.

This is the check that finds the module written, tested and never called.
It happens more than anybody expects: a rule gets implemented, a test gets
written against it directly, and nothing in the package ever reaches it, so
the rule is not in force anywhere and the suite is green.

A name counts as wired if it is used anywhere outside the file that defines
it: another module, a test, or the console script. The tests count on
purpose. A helper that only the tests call is still a helper somebody wrote
for a reason, and the check that finds *those* is coverage, not this one.

A function attached to the console script by a decorator is wired by that
decorator and never by name, so those are left out. Whether a command is
reachable is what `check_help` is for.

Only functions are looked at. A constant is defined to be named, and naming
one for the sake of the module it is in is the point of it, so a constant
that nothing outside refers to is not dead. A class returned by a function
is not dead either: nothing has to say its name to use it.
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict

from culmbin.tools.sources import Module, public, relative, report, source_modules, test_modules

EXEMPT = frozenset(
    {
        "main",
        "run",
        "cli",
        "problems",
    }
)
"""Names CI calls rather than the package: every check's entry points."""


def _defined(module: Module) -> list[tuple[str, int]]:
    """Every public top level function a module defines, with its line."""
    return [
        (node.name, node.lineno)
        for node in module.tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and public(node.name)
        and not _is_command(node)
    ]


def _is_command(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether a function is attached to the console script by a decorator."""
    for decorator in node.decorator_list:
        call = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = call.attr if isinstance(call, ast.Attribute) else getattr(call, "id", "")
        if name in {"command", "group"}:
            return True
    return False


def _used_elsewhere() -> dict[str, set[str]]:
    """Every name used, by the module that uses it."""
    used: dict[str, set[str]] = defaultdict(set)
    for module in [*source_modules(), *test_modules()]:
        for name in module.names():
            used[name].add(str(module.path))
        for node in ast.walk(module.tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    used[alias.name].add(str(module.path))
    return used


def problems() -> list[str]:
    """Every public name nothing outside its own module refers to."""
    used = _used_elsewhere()
    found = []
    for module in source_modules():
        where = str(module.path)
        for name, line in _defined(module):
            if name in EXEMPT:
                continue
            others = used.get(name, set()) - {where}
            if not others:
                found.append(
                    f"{relative(module.path)}:{line}: {name} is defined and "
                    f"nothing else refers to it."
                )
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "wiring")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
