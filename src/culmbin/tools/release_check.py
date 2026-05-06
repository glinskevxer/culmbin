"""Everything that makes a bad release day, asked before anybody ships.

None of these is wrong until somebody tries to cut a version, which is
exactly why they are worth one command that can be run on a quiet Tuesday.

- the version in the package and the version in `pyproject.toml` agree
- the changelog has an entry for that version
- the changelog's newest entry is the version being shipped
- the schema is at the version the migrations say it is
- the pins and the constraints still agree, because a release ships the
  closure and not the direct pins
- the changelog entry names the schema version it ships

The last one is the one that was added after a release went out whose
migrations nobody had mentioned. A version that changes the schema and does
not say so is a version somebody upgrades to on a Friday afternoon without
taking a backup first.
"""

from __future__ import annotations

import re
import sys

from culmbin import __version__
from culmbin.store.book import MEMORY, Book
from culmbin.store.migrations import current_version, latest_version, migrate
from culmbin.tools.check_package import problems as package_problems
from culmbin.tools.sources import project_root, report

VERSION_LINE = re.compile(r'^version = "([^"]+)"\s*$', re.MULTILINE)
CHANGELOG_HEADING = re.compile(r"^## (\d+\.\d+\.\d+)", re.MULTILINE)
SCHEMA_LINE = re.compile(r"schema version (\d+)", re.IGNORECASE)
STAMP = "1970-01-01T00:00:00+00:00"


def declared_version() -> str | None:
    """The version in `pyproject.toml`."""
    text = (project_root() / "pyproject.toml").read_text(encoding="utf-8")
    match = VERSION_LINE.search(text)
    return None if match is None else match.group(1)


def changelog_versions() -> list[str]:
    """Every version the changelog has an entry for, newest first."""
    path = project_root() / "CHANGELOG.md"
    if not path.exists():
        return []
    return CHANGELOG_HEADING.findall(path.read_text(encoding="utf-8"))


def newest_entry() -> str:
    """The text of the newest changelog entry, heading and all."""
    path = project_root() / "CHANGELOG.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    parts = text.split("\n## ")
    return "" if len(parts) < 2 else parts[1]


def schema_named() -> int | None:
    """The schema version the newest changelog entry says it ships."""
    match = SCHEMA_LINE.search(newest_entry())
    return None if match is None else int(match.group(1))


def problems() -> list[str]:
    """Everything that would make this a bad day to cut a release."""
    found = []
    declared = declared_version()
    if declared is None:
        found.append("pyproject.toml: there is no version in it.")
    elif declared != __version__:
        found.append(f"the package says {__version__} and pyproject.toml says {declared}.")
    entries = changelog_versions()
    if not entries:
        found.append("CHANGELOG.md: there are no version entries in it.")
    elif __version__ not in entries:
        found.append(f"CHANGELOG.md: there is no entry for {__version__}.")
    elif entries[0] != __version__:
        found.append(
            f"CHANGELOG.md: the newest entry is {entries[0]} and the package is {__version__}."
        )
    named = schema_named()
    if entries and named is None:
        found.append(
            f"CHANGELOG.md: the entry for {entries[0]} does not say which schema it ships."
        )
    elif named is not None and named != latest_version():
        found.append(
            f"CHANGELOG.md: the entry says schema version {named} and the migrations "
            f"are at {latest_version()}."
        )
    found.extend(package_problems())
    with Book.open(MEMORY) as book:
        migrate(book, STAMP)
        if current_version(book) != latest_version():
            found.append("a fresh book does not come out at the latest schema version.")
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "release")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
