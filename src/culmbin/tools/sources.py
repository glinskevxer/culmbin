"""Reading the source tree, without importing it.

Everything here is `ast` over files on disk. The checks above it are then
about what the tree says rather than about what the interpreter managed to
load, which is the difference between finding a broken module and crashing
on one.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

PACKAGE = "culmbin"


def package_root() -> Path:
    """The directory the package lives in."""
    return Path(__file__).resolve().parent.parent


def project_root() -> Path:
    """The directory the project lives in, which holds `pyproject.toml`."""
    return package_root().parent.parent


def tests_root() -> Path:
    """The directory the tests live in."""
    return project_root() / "tests"


@dataclass(frozen=True, slots=True)
class Module:
    """One source file, parsed."""

    path: Path
    tree: ast.Module

    @property
    def dotted(self) -> str:
        """The module's import name, `culmbin.units.mass` style."""
        relative = self.path.relative_to(package_root().parent).with_suffix("")
        parts = relative.parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)

    @property
    def layer(self) -> str:
        """Which layer the module belongs to, which is its first subpackage."""
        parts = self.dotted.split(".")
        return parts[1] if len(parts) > 1 else ""

    @property
    def docstring(self) -> str | None:
        """The module docstring, if it has one."""
        return ast.get_docstring(self.tree)

    def imports(self) -> Iterator[str]:
        """Every module this one imports from, dotted."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                yield node.module

    def definitions(self) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
        """Every function and class defined anywhere in the module."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                yield node

    def top_level(self) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
        """Every function and class defined at the top of the module."""
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                yield node

    def names(self) -> Iterator[str]:
        """Every name used anywhere in the module."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                yield node.id
            elif isinstance(node, ast.Attribute):
                yield node.attr


def read(path: Path) -> Module:
    """Parse one file."""
    return Module(path=path, tree=ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))


def source_modules() -> list[Module]:
    """Every module in the package, in path order."""
    return [read(path) for path in sorted(package_root().rglob("*.py"))]


def test_modules() -> list[Module]:
    """Every module under `tests`, in path order."""
    return [read(path) for path in sorted(tests_root().rglob("*.py"))]


def public(name: str) -> bool:
    """Whether a name is part of the interface rather than an implementation."""
    return not name.startswith("_")


def relative(path: Path) -> str:
    """A path as it should be printed in a message."""
    try:
        return str(path.relative_to(project_root()))
    except ValueError:  # pragma: no cover
        return str(path)


def report(problems: list[str], what: str) -> int:
    """Print a check's problems and give back an exit status.

    Every check ends with this, so they all print the same shape and a
    reader of a CI log does not have to work out which one is talking.
    """
    if not problems:
        print(f"{what}: nothing to report.")
        return 0
    for problem in problems:
        print(problem)
    print(f"{what}: {len(problems)} to fix.")
    return 1
