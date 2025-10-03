"""Writing the whole book out as CSV, one file per table.

The list of tables comes off the book rather than out of this module. A
table added by a migration and not added to a hand written list is a table
that quietly stops being exported, and nobody finds out until the year the
export is the only copy left.
"""

from __future__ import annotations

import csv
from pathlib import Path

from culmbin.errors import ConflictError
from culmbin.store.book import Book

SKIP = frozenset({"schema_version"})
"""Tables the export leaves out, because they describe the book rather than
what is in it."""


def export_book(book: Book, into: Path) -> tuple[Path, ...]:
    """Write every table to its own CSV file and say what was written.

    Refuses to write into a directory that already has CSV files in it. An
    export half over an older one is a set of files nobody can date.
    """
    into.mkdir(parents=True, exist_ok=True)
    existing = sorted(into.glob("*.csv"))
    if existing:
        raise ConflictError(f"{into} already holds {len(existing)} csv files")
    written = []
    for table in book.tables():
        if table in SKIP:
            continue
        columns = book.columns(table)
        rows = book.query(f'SELECT * FROM "{table}"')
        path = into / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([row[column] for column in columns])
        written.append(path)
    return tuple(written)


def exportable(book: Book) -> tuple[str, ...]:
    """Every table the export would write, in name order."""
    return tuple(table for table in book.tables() if table not in SKIP)
