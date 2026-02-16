"""A migration that has shipped never changes, and this is what says so.

Editing a migration is the most expensive mistake in this package, and it is
invisible. The code goes on working, the tests go on passing, and every book
that was created before the edit has a schema that does not match the code
any more. Nobody finds out until a query fails on a book that has been open
since March.

So every migration's script is fingerprinted into `migrations.lock` the
first time it is written, and this check compares. A changed script fails.
A new one appended is fine and is written into the lock by running this with
`--write`.

Deleting or reordering fails too, and for the same reason: version seven has
been applied to books that exist, and what version seven did is a fact about
those books rather than a decision this package still gets to make.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from culmbin.store.migrations import MIGRATIONS
from culmbin.tools.sources import project_root, report

LOCK = "migrations.lock"
HEADING = "# every migration that has shipped, and what it was"


def fingerprint(script: str) -> str:
    """A short hash of a migration script.

    Whitespace is not stripped. A migration reformatted is a migration
    changed as far as this is concerned, because the only way to be sure a
    reformat changed nothing is to have not done it.
    """
    return hashlib.sha256(script.encode("utf-8")).hexdigest()[:16]


def lock_path() -> Path:
    """Where the lock lives."""
    return project_root() / LOCK


def render() -> str:
    """The lock as it should be for the migrations that exist now."""
    lines = [
        HEADING,
        "#",
        "# Written by `python -m culmbin.tools.check_migrations --write`.",
        "# A line here never changes. A new line is appended when a migration is.",
    ]
    for migration in MIGRATIONS:
        lines.append(f"{migration.version:3d}  {fingerprint(migration.script)}  {migration.name}")
    return "\n".join(lines) + "\n"


def recorded() -> dict[int, tuple[str, str]]:
    """Every migration in the lock, by version, as a fingerprint and a name."""
    path = lock_path()
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        version, digest, name = line.split(maxsplit=2)
        out[int(version)] = (digest, name)
    return out


def problems() -> list[str]:
    """Every migration that has changed, gone, or moved."""
    if not lock_path().exists():
        return [f"{LOCK}: there is no lock. Write one with --write."]
    locked = recorded()
    have = {migration.version: migration for migration in MIGRATIONS}
    found = []
    for version, (digest, name) in sorted(locked.items()):
        migration = have.get(version)
        if migration is None:
            found.append(f"{LOCK}: migration {version} ({name}) has gone, and books have it.")
            continue
        if fingerprint(migration.script) != digest:
            found.append(
                f"{LOCK}: migration {version} ({name}) has changed, and books have the old one."
            )
        elif migration.name != name:
            found.append(f"{LOCK}: migration {version} was {name!r} and is now {migration.name!r}.")
    return found


def unlocked() -> list[int]:
    """Every migration written since the lock was, in order."""
    locked = set(recorded())
    return [migration.version for migration in MIGRATIONS if migration.version not in locked]


def main(argv: list[str] | None = None) -> int:
    """Check the lock, or write it."""
    parser = argparse.ArgumentParser(description="hold the migrations still")
    parser.add_argument("--write", action="store_true", help="record the migrations as they are")
    arguments = parser.parse_args(argv)
    if arguments.write:
        lock_path().write_text(render(), encoding="utf-8")
        print(f"migrations: wrote {LOCK} with {len(MIGRATIONS)} migrations.")
        return 0
    found = problems()
    if not found:
        new = unlocked()
        if new:
            print(f"migrations: {len(new)} new, run --write to record them.")
            return 1
    return report(found, "migrations")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
