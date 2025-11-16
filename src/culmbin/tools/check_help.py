"""Every command says what it does, and every option says what it is for.

A console script is only as good as `--help`, and `--help` is built out of
docstrings and `help=` strings. A command with neither is a command nobody
outside this office can run.

The check walks the click tree by importing the console script, which is the
one place in `tools` that imports rather than reads. That is unavoidable: a
click group is built by decorators at import time and there is nothing in
the source text that says what the tree came out as.
"""

from __future__ import annotations

import sys

import click

from culmbin.cli.main import cli
from culmbin.tools.sources import report

MINIMUM_WORDS = 3


def walk(command: click.Command, path: str = "") -> list[tuple[str, click.Command]]:
    """Every command in the tree, with the words somebody would type."""
    here = f"{path} {command.name}".strip()
    out = [(here, command)]
    if isinstance(command, click.Group):
        for name in sorted(command.commands):
            out.extend(walk(command.commands[name], here))
    return out


def command_names() -> tuple[str, ...]:
    """Every command line the console script accepts, in order."""
    return tuple(path for path, _ in walk(cli))


def problems() -> list[str]:
    """Every command or option with nothing useful to say about itself."""
    found = []
    for path, command in walk(cli):
        text = (command.help or "").strip()
        if not text:
            found.append(f"{path}: has no help.")
        elif len(text.split()) < MINIMUM_WORDS:
            found.append(f"{path}: has {len(text.split())} words of help.")
        for parameter in command.params:
            if not isinstance(parameter, click.Option):
                continue
            if parameter.name in {"help", "version"}:
                continue
            if not (parameter.help or "").strip() and not parameter.required:
                found.append(
                    f"{path}: the optional --{(parameter.name or '').replace('_', '-')} "
                    f"says nothing about itself."
                )
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "help")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
