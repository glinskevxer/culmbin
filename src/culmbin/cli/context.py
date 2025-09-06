"""What every command is given.

This is its own module so that the command groups can import it without
importing the group they are about to be attached to, which would be a
circle. It is four fields and two methods and it is not worth more than
that.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import click

from culmbin.store.book import Book
from culmbin.store.migrations import migrate

DEFAULT_BOOK = "culmbin.sqlite3"


@dataclass
class Context:
    """A path, a day, and a book once something asks for one."""

    path: str
    on: dt.date
    _book: Book | None = None

    def book(self) -> Book:
        """Open the book, migrate it, and keep it for the rest of the command."""
        if self._book is None:
            book = Book.open(self.path)
            migrate(book, self.stamp)
            self._book = book
        return self._book

    def close(self) -> None:
        """Close the book if one was opened."""
        if self._book is not None:
            self._book.close()
            self._book = None

    @property
    def stamp(self) -> str:
        """The day, as a migration stamps itself."""
        return f"{self.on.isoformat()}T00:00:00+00:00"


pass_context = click.make_pass_decorator(Context)


def echo_lines(lines: list[str]) -> None:
    """Print a block of lines, which is what most commands produce."""
    for line in lines:
        click.echo(line)
