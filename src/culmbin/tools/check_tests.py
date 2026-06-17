"""Every source module has a test module, and every test module has a source.

The first half is the obvious one. The second half is the one that finds
things: a test module left behind after the code it tested was renamed goes
on passing forever and nobody reads it again.

`tests/support` is exempt from the second half, because it is builders
rather than tests, and `cli/main.py` is exempt from neither.
"""

from __future__ import annotations

import sys
from pathlib import Path

from culmbin.tools.sources import package_root, relative, report, tests_root

NO_TEST_NEEDED = frozenset(
    {
        "culmbin",
        "culmbin.blend",
        "culmbin.cli",
        "culmbin.intake",
        "culmbin.model",
        "culmbin.process",
        "culmbin.report",
        "culmbin.sales",
        "culmbin.store",
        "culmbin.tools",
        "culmbin.trace",
        "culmbin.units",
    }
)
"""Package `__init__` modules, which hold a docstring and re-exports."""

SUPPORT = frozenset({"tests.support", "tests.conftest", "tests.cli.setup"})
"""Test helpers, which are not tests and do not test anything."""

CROSS_CUTTING = frozenset({"test_calendar.py", "test_layout_notes.py", "test_invariants.py"})
"""Test modules that are about the package rather than about one module.

`test_calendar.py` sweeps the clock across three years and asks every rule
that takes a day. There is no `calendar.py` for it to be paired with and
there should not be: the point of it is that the rules are spread over a
dozen modules and none of them may move with the date.

`test_layout_notes.py` is about one function in `report.layout` and the ten
pages that use it, which is why it does not live in `test_layout.py`.

`test_invariants.py` sweeps every conversion in `units` over its whole range
and checks the properties rather than the numbers, so it pairs with all four
modules and with none of them.
"""


def _expected_test(path: Path) -> Path:
    """Where the test module for a source module should be."""
    relative_path = path.relative_to(package_root())
    return tests_root() / relative_path.parent / f"test_{relative_path.name}"


def _dotted(path: Path, root: Path, prefix: str) -> str:
    """A path under a root, as a dotted name."""
    parts = path.relative_to(root).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join((prefix, *parts)) if parts else prefix


def missing_tests() -> list[str]:
    """Every source module with no test module against it."""
    found = []
    for path in sorted(package_root().rglob("*.py")):
        dotted = _dotted(path, package_root(), "culmbin")
        if dotted in NO_TEST_NEEDED:
            continue
        wanted = _expected_test(path)
        if not wanted.exists():
            found.append(f"{relative(path)}: nothing at {relative(wanted)} tests it.")
    return found


def orphaned_tests() -> list[str]:
    """Every test module whose source module has gone."""
    found = []
    for path in sorted(tests_root().rglob("test_*.py")):
        if path.name in CROSS_CUTTING:
            continue
        source = package_root() / path.relative_to(tests_root()).parent / path.name[len("test_") :]
        if not source.exists():
            found.append(f"{relative(path)}: nothing at {relative(source)} is left to test.")
    return found


def problems() -> list[str]:
    """Both halves, in one list."""
    return [*missing_tests(), *orphaned_tests()]


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "tests")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
