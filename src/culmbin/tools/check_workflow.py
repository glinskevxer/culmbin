"""The walk in CI is a shell script inside yaml, and nothing compiles it.

Two things go wrong with a walk, and both of them go wrong quietly.

A command gets renamed and the walk goes on naming the old one, so CI goes
red on a Tuesday for a reason nobody can find in the diff. This check looks
every command in the walk up in the click tree.

A check gets written and nobody adds it to CI, so it runs locally and never
in anger. This check reads the workflow for the checks it runs and compares
that with the checks that exist.

The yaml is read as text on purpose. There is no yaml parser in this
package's dependencies and adding one to read one file would be a poor
trade, so the two things this needs are found by looking for the words.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from culmbin.tools.check_help import command_names
from culmbin.tools.sources import package_root, project_root, report

WORKFLOW = "ci.yml"
RUNS_CHECK = re.compile(r"python -m culmbin\.tools\.(check_\w+)")
CONTINUES = ("\\", "--", "&&", "|")


def workflow_path() -> Path:
    """Where the workflow lives."""
    return project_root() / ".github" / "workflows" / WORKFLOW


def _lines() -> list[str]:
    """Every line of the workflow, stripped."""
    return [line.strip() for line in workflow_path().read_text(encoding="utf-8").splitlines()]


def walk_commands() -> list[str]:
    """Every `culmbin` command line the walk runs, joined over continuations."""
    out = []
    buffer = ""
    for line in _lines():
        if buffer:
            buffer = f"{buffer} {line.rstrip(chr(92)).strip()}"
        elif line.startswith("culmbin "):
            buffer = line.rstrip("\\").strip()
        else:
            continue
        if not line.endswith("\\"):
            out.append(buffer)
            buffer = ""
    return out


def _words(command: str) -> list[str]:
    """The command words of a walk line, without options or their values."""
    words = []
    skip = False
    for token in command.split()[1:]:
        if skip:
            skip = False
            continue
        if token.startswith("--"):
            skip = "=" not in token
            continue
        words.append(token)
    return words


def unknown_commands() -> list[str]:
    """Every command the walk runs that the console script does not have."""
    known = set(command_names())
    found = []
    for command in walk_commands():
        words = _words(command)
        best = ""
        for depth in range(1, len(words) + 1):
            candidate = "cli " + " ".join(words[:depth])
            if candidate in known:
                best = candidate
        if not best:
            found.append(
                f"{WORKFLOW}: the walk runs {' '.join(words[:2])!r}, which is not a command."
            )
    return found


def checks_not_run() -> list[str]:
    """Every check module CI does not run."""
    text = workflow_path().read_text(encoding="utf-8")
    run = set(RUNS_CHECK.findall(text))
    have = {path.stem for path in package_root().glob("tools/check_*.py")}
    return [f"{WORKFLOW}: does not run {name}." for name in sorted(have - run)]


def problems() -> list[str]:
    """Both halves, in one list."""
    if not workflow_path().exists():
        return [f"{WORKFLOW}: there is no workflow at {workflow_path()}."]
    return [*unknown_commands(), *checks_not_run()]


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "workflow")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
