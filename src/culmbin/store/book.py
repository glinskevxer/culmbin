"""The book, which is one SQLite file.

Two decisions here are worth writing down because both of them were made
after the alternative had been tried.

**The connection runs in autocommit.** Python's sqlite3 module opens a
transaction for you on the first write statement and leaves it open until
something commits, which means a single write followed by a crash, or by
nothing at all, is lost. Every test still passes, because a test reads back
through the same connection that wrote. Autocommit plus an explicit
`writing()` block for anything multi statement is the shape that does not
have that failure in it.

**Foreign keys are on.** SQLite has them off by default, per connection,
every time. A book opened without that pragma will happily delete a delivery
that a piece is built out of.

**Scripts are split and run statement by statement.** Python's
`Connection.executescript` commits any open transaction before it starts.
That is documented and it is still a trap, because it means a migration
running inside a `writing` block ends the transaction under the caller and
the eventual `COMMIT` fails with no transaction active. Splitting the script
here keeps a migration atomic, which is the one place it has to be.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any

from culmbin.errors import ConflictError, NotFoundError, StateError

Params = Sequence[Any] | Mapping[str, Any]

MEMORY = ":memory:"
"""What to pass as a path for a book that is not on disk at all."""


class Book:
    """An open book.

    Use it as a context manager, or call `close`. A book that is never
    closed leaves a connection open, which on 3.13 is a `ResourceWarning`
    blamed on whichever test the collector happened to be running.
    """

    def __init__(self, path: str, connection: sqlite3.Connection) -> None:
        self.path = path
        self._connection = connection
        self._closed = False
        self._depth = 0

    @classmethod
    def open(cls, path: str | Path) -> Book:
        """Open or create a book at a path, or in memory."""
        text = str(path)
        connection = sqlite3.connect(text, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return cls(text, connection)

    @property
    def closed(self) -> bool:
        """Whether this book has been closed."""
        return self._closed

    @property
    def connection(self) -> sqlite3.Connection:
        """The connection underneath, for the few callers that need it."""
        self._check_open()
        return self._connection

    def _check_open(self) -> None:
        if self._closed:
            raise StateError(f"the book at {self.path} is closed")

    def close(self) -> None:
        """Close the book. Closing a closed book is not an error."""
        if not self._closed:
            self._connection.close()
            self._closed = True

    def __enter__(self) -> Book:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def execute(self, sql: str, params: Params = ()) -> sqlite3.Cursor:
        """Run one statement, translating the constraint failures worth naming."""
        self._check_open()
        try:
            return self._connection.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise _translate(exc) from exc

    def executemany(self, sql: str, rows: Sequence[Params]) -> sqlite3.Cursor:
        """Run one statement over many parameter sets."""
        self._check_open()
        try:
            return self._connection.executemany(sql, rows)
        except sqlite3.IntegrityError as exc:
            raise _translate(exc) from exc

    def executescript(self, sql: str) -> None:
        """Run a whole script, one statement at a time.

        This is deliberately not `Connection.executescript`, which commits
        whatever transaction is open before it runs anything. A migration
        that did that would not be atomic, and the failure it produces is a
        commit error a long way from the cause.
        """
        self._check_open()
        for statement in split_statements(sql):
            self.execute(statement)

    def query(self, sql: str, params: Params = ()) -> list[sqlite3.Row]:
        """Every row a statement selects."""
        return self.execute(sql, params).fetchall()

    def first(self, sql: str, params: Params = ()) -> sqlite3.Row | None:
        """The first row, or nothing."""
        row: sqlite3.Row | None = self.execute(sql, params).fetchone()
        return row

    def one(self, sql: str, params: Params = (), what: str = "record") -> sqlite3.Row:
        """The first row, or say what was being looked for."""
        row = self.first(sql, params)
        if row is None:
            raise NotFoundError(f"the book holds no {what} matching that")
        return row

    def scalar(self, sql: str, params: Params = ()) -> Any:
        """The first column of the first row, which is what a count is."""
        row = self.first(sql, params)
        return None if row is None else row[0]

    @contextmanager
    def writing(self) -> Iterator[Book]:
        """Group several statements so they land together or not at all.

        Nesting is allowed and the inner block does nothing, because half the
        callers here are functions that are sometimes called on their own and
        sometimes called from something that is already writing.
        """
        self._check_open()
        if self._depth > 0:
            self._depth += 1
            try:
                yield self
            finally:
                self._depth -= 1
            return
        self._connection.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield self
        except BaseException:
            self._depth = 0
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._depth = 0
            self._connection.execute("COMMIT")

    @property
    def in_transaction(self) -> bool:
        """Whether a `writing` block is open."""
        return self._depth > 0

    def tables(self) -> tuple[str, ...]:
        """Every table in the book, in name order, without sqlite's own."""
        rows = self.query(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return tuple(str(row["name"]) for row in rows)

    def columns(self, table: str) -> tuple[str, ...]:
        """Every column of a table, in the order it was declared."""
        rows = self.query(f'PRAGMA table_info("{_identifier(table)}")')
        if not rows:
            raise NotFoundError(f"no table called {table!r}")
        return tuple(str(row["name"]) for row in rows)

    def backup_to(self, path: str | Path) -> None:
        """Copy the whole book somewhere, through SQLite rather than the filesystem.

        Copying the file with `cp` while anything is writing gives a copy
        that is a valid file and the wrong contents. This does not.
        """
        self._check_open()
        with sqlite3.connect(str(path)) as target:
            self._connection.backup(target)
        target.close()


def split_statements(script: str) -> tuple[str, ...]:
    """Split a script into complete statements.

    `sqlite3.complete_statement` is the same check the command line shell
    uses, so it gets strings, comments and trigger bodies right, which a
    plain split on semicolons does not. The split is still on semicolons,
    because that is where a statement can end, but a piece is only taken as
    a statement once SQLite agrees it is one.

    A last statement with no semicolon after it is allowed, because that is
    how everybody writes a one line script.
    """
    statements = []
    buffer = ""
    pieces = script.split(";")
    for piece in pieces[:-1]:
        buffer += piece + ";"
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ""
    tail = (buffer + pieces[-1]).strip()
    if tail:
        if not sqlite3.complete_statement(tail + ";"):
            raise StateError(f"the script ends in the middle of a statement: {tail[:60]!r}")
        statements.append(tail)
    return tuple(statements)


def _identifier(name: str) -> str:
    """Check a table name before it goes anywhere near a statement.

    Everything else in the package reaches SQLite as a parameter. Table names
    cannot be parameters, so the short list of places that interpolate one go
    through here, and the caller quotes what comes back. Both halves are
    needed: `nothing` is alphanumeric and it is also a SQLite keyword, so it
    passes this and still has to be quoted to parse.
    """
    if not name.replace("_", "").isalnum():
        raise NotFoundError(f"{name!r} is not a table name")
    return name


def _translate(exc: sqlite3.IntegrityError) -> Exception:
    """Turn the constraint failures worth naming into our own exceptions."""
    text = str(exc)
    if "UNIQUE" in text:
        return ConflictError(f"the book already holds this: {text}")
    if "FOREIGN KEY" in text:
        return ConflictError(f"this refers to something the book does not hold: {text}")
    return ConflictError(text)
