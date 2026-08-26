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

from culmbin.store.book import WAIT_SECONDS, Book
from culmbin.store.journal import UNKNOWN, record
from culmbin.store.migrations import migrate

DEFAULT_BOOK = "culmbin.sqlite3"


@dataclass
class Context:
    """A path, a day, who is at the keyboard, and a book once one is asked for."""

    path: str
    on: dt.date
    actor: str = UNKNOWN
    wait_seconds: float = WAIT_SECONDS
    _book: Book | None = None

    def book(self) -> Book:
        """Open the book, migrate it, and keep it for the rest of the command."""
        if self._book is None:
            book = Book.open(self.path, self.wait_seconds)
            migrate(book, self.stamp)
            self._book = book
        return self._book

    def book_as_is(self) -> Book:
        """Open the book without migrating it.

        For the one command that has to report what an upgrade *would* do.
        Asking for `book()` first would migrate it and then report that
        there was nothing to apply, which is true and useless.
        """
        if self._book is None:
            self._book = Book.open(self.path, self.wait_seconds)
        return self._book

    def close(self) -> None:
        """Close the book if one was opened."""
        if self._book is not None:
            self._book.close()
            self._book = None

    def note(self, action: str, subject: str, detail: str = "") -> None:
        """Write in the journal that this command did something.

        Every command that changes the book calls this, and no command that
        only reads it does. That is the whole rule: the journal is what was
        done, and looking at something is not doing anything to it.
        """
        record(self.book(), self.on, self.actor, action, subject, detail)

    @property
    def stamp(self) -> str:
        """The day, as a migration stamps itself."""
        return f"{self.on.isoformat()}T00:00:00+00:00"


pass_context = click.make_pass_decorator(Context)


def echo_lines(lines: list[str]) -> None:
    """Print a block of lines, which is what most commands produce."""
    for line in lines:
        click.echo(line)
