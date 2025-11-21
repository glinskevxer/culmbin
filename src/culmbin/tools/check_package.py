"""The pins in `pyproject.toml` are all in `constraints.txt`, at the same version.

Two files list versions and they are not the same list: one is what this
package asks for and the other is the closure CI installs. They agree about
everything they both mention, and the moment they stop agreeing the build
that installs the constraints is testing something the package did not ask
for.

Both files are read as text. Adding a toml parser to read four lines would
be a poor trade, and the shape of what is being read is a pinned requirement
either way.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from culmbin.tools.sources import project_root, report

PIN = re.compile(r'^\s*"?([A-Za-z0-9_.\-]+)==([0-9][^"\s,]*)"?,?\s*$')
NAME = re.compile(r"[-_.]+")


def normalise(name: str) -> str:
    """A distribution name as pip compares them, which ignores dashes."""
    return NAME.sub("-", name).lower()


def _pins(path: Path) -> dict[str, str]:
    """Every `name==version` in a file, by normalised name."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = PIN.match(line)
        if match:
            out[normalise(match.group(1))] = match.group(2)
    return out


def declared() -> dict[str, str]:
    """What `pyproject.toml` asks for."""
    return _pins(project_root() / "pyproject.toml")


def constrained() -> dict[str, str]:
    """What `constraints.txt` installs."""
    return _pins(project_root() / "constraints.txt")


def problems() -> list[str]:
    """Every pin that is missing from the closure or disagrees with it."""
    asked = declared()
    installed = constrained()
    found = []
    for name, version in sorted(asked.items()):
        if name == "hatchling":
            continue
        if name not in installed:
            found.append(f"constraints.txt: {name} is asked for and not constrained.")
        elif installed[name] != version:
            found.append(
                f"constraints.txt: {name} is constrained to {installed[name]} "
                f"and asked for at {version}."
            )
    if not asked:
        found.append("pyproject.toml: nothing is pinned, so nothing is being checked.")
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "package")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
