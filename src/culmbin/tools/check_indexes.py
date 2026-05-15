"""Every foreign key has an index on the column that points.

SQLite indexes the column being pointed *at*, because it has to be unique.
It does not index the column doing the pointing, and every join and every
cascade in the package goes the other way. On a book with four hundred
thousand rows in it the difference is a report that takes a second and a
report that takes a minute, and nobody notices until the book is big, by
which time nobody remembers which query it was.

The check builds a fresh book from the migrations and reads the schema out
of it, so it is asking the schema that ships rather than a list somebody
wrote down.

An index whose *first* column is the pointing column counts. SQLite can use
a composite index for a lookup on its leading column, and half the indexes
in this book are composite for the sake of the order things come back in.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from culmbin.store.book import MEMORY, Book
from culmbin.store.migrations import migrate
from culmbin.tools.sources import report

STAMP = "1970-01-01T00:00:00+00:00"

EXEMPT = frozenset(
    {
        ("silo_receipt", "ticket"),
        ("malt_lot", "analysis"),
        ("piece", "programme"),
        ("piece", "schedule"),
        ("piece", "curve"),
        ("kiln_run", "piece"),
        ("cleaning_interval", "vessel"),
        ("grading", "ticket"),
    }
)
"""Keys that are already the primary key or a unique column of their table.

SQLite indexes those for free, so asking for a second index on them would be
asking for a duplicate.
"""


@dataclass(frozen=True, slots=True)
class Key:
    """One foreign key, and the column it points from."""

    table: str
    column: str
    points_at: str

    def __str__(self) -> str:
        return f"{self.table}.{self.column} -> {self.points_at}"


def keys(book: Book) -> list[Key]:
    """Every foreign key in a book, in table order."""
    found = []
    for table in book.tables():
        for row in book.foreign_keys(table):
            found.append(Key(table, str(row["from"]), str(row["table"])))
    return found


def leading_columns(book: Book, table: str) -> set[str]:
    """The first column of every index on a table, and its primary key."""
    leading = set()
    for row in book.indexes(table):
        columns = book.index_columns(str(row["name"]))
        if columns:
            leading.add(columns[0])
    for row in book.column_details(table):
        if row["pk"]:
            leading.add(str(row["name"]))
    return leading


def problems() -> list[str]:
    """Every foreign key with nothing indexing the column it points from."""
    found = []
    with Book.open(MEMORY) as book:
        migrate(book, STAMP)
        for key in keys(book):
            if (key.table, key.column) in EXEMPT:
                continue
            if key.column not in leading_columns(book, key.table):
                found.append(
                    f"{key}: nothing indexes {key.column}, so every join and every "
                    f"cascade over it is a scan."
                )
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "indexes")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
