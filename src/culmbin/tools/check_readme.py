"""The README and the design note name code, so a machine can say when they rot.

Both documents point at modules, at commands and at the generated documents
next to them. Every one of those is a thing that can be renamed, and when it
is the prose goes on describing something that is not there.

So: every dotted name in backticks resolves to a module or an attribute of
one, every `culmbin ...` command is a command, and every document referred
to exists. Anything else in backticks is prose and is left alone.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

from culmbin.tools.check_help import command_names
from culmbin.tools.sources import project_root, report

DOCUMENTS = ("README.md", "docs/design.md", "CHANGELOG.md")
BACKTICKED = re.compile(r"`([^`\n]+)`")
DOTTED = re.compile(r"^culmbin(\.[a-z_][a-z0-9_]*)+$")
COMMAND = re.compile(r"^culmbin ([a-z][a-z\- ]*)")
DOCUMENT_LINK = re.compile(r"^(docs/[a-z_]+\.md|[A-Z]+\.md)$")


def _resolves(dotted: str) -> bool:
    """Whether a dotted name is a module, or an attribute of one."""
    try:
        importlib.import_module(dotted)
    except ImportError:
        head, _, tail = dotted.rpartition(".")
        try:
            return hasattr(importlib.import_module(head), tail)
        except ImportError:
            return False
    return True


def _command_words(text: str) -> str:
    """The command words out of a `culmbin ...` snippet, options dropped."""
    words = []
    for token in text.split()[1:]:
        if token.startswith("-") or token.upper() == token:
            break
        words.append(token)
    return "cli " + " ".join(words)


def _check(path: Path) -> list[str]:
    """Every stale reference in one document."""
    if not path.exists():
        return [f"{path.name}: there is no such document."]
    known = set(command_names())
    problems = []
    for quoted in BACKTICKED.findall(path.read_text(encoding="utf-8")):
        text = quoted.strip()
        if DOTTED.match(text):
            if not _resolves(text):
                problems.append(f"{path.name}: names {text}, which is not there any more.")
        elif COMMAND.match(text):
            wanted = _command_words(text)
            if wanted.strip() != "cli" and wanted not in known:
                problems.append(f"{path.name}: names the command {text!r}, which is not one.")
        elif DOCUMENT_LINK.match(text) and not (project_root() / text).exists():
            problems.append(f"{path.name}: points at {text}, which is not there.")
    return problems


def problems() -> list[str]:
    """Every stale reference in the hand written documents."""
    found = []
    for name in DOCUMENTS:
        found.extend(_check(project_root() / name))
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "readme")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
