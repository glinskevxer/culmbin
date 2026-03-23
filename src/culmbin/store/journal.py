"""An append-only journal of what was done, by whom, and to what.

The book already says what is true now. The journal says how it got that
way, which is a different question and the one an auditor asks.

**It is append only, and the book enforces it.** There are two triggers on
the table that abort an update or a delete, so a journal entry cannot be
corrected. That is the whole value of it: a record that can be tidied up is
a record nobody outside the office has any reason to believe.

An entry is four things: the day, who, what they did, and what they did it
to. The detail is free text and nothing reads it, which is deliberate. The
moment something parses the detail, the detail has a format, and the next
person to write an entry gets it wrong.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass

from culmbin.errors import ConflictError, ValidationError
from culmbin.store.book import Book
from culmbin.store.query import narrowing
from culmbin.store.rows import as_count, as_date, as_text, date_text

UNKNOWN = "unknown"
"""Who did it when nobody said.

Recorded rather than left out. An entry with nobody against it is still an
entry, and pretending the work did not happen is worse than admitting the
name was not asked for.
"""


@dataclass(frozen=True, slots=True)
class Entry:
    """One thing somebody did."""

    seq: int
    on: dt.date
    actor: str
    action: str
    subject: str
    detail: str = ""

    def __str__(self) -> str:
        tail = f": {self.detail}" if self.detail else ""
        return f"{self.on.isoformat()}  {self.actor:<10}{self.action} {self.subject}{tail}"


def _entry(row: sqlite3.Row) -> Entry:
    """Turn a row into an entry."""
    return Entry(
        seq=as_count(row, "seq"),
        on=as_date(row, "on_day"),
        actor=as_text(row, "actor"),
        action=as_text(row, "action"),
        subject=as_text(row, "subject"),
        detail=as_text(row, "detail"),
    )


def record(
    book: Book, on: dt.date, actor: str, action: str, subject: str, detail: str = ""
) -> Entry:
    """Write down that somebody did something."""
    for name, value in (("action", action), ("subject", subject)):
        if not value.strip():
            raise ValidationError(f"a journal entry needs {name} and this one has none")
    who = actor.strip() or UNKNOWN
    cursor = book.execute(
        "INSERT INTO entry (on_day, actor, action, subject, detail) VALUES (?, ?, ?, ?, ?)",
        (date_text(on), who, action.strip(), subject.strip(), detail.strip()),
    )
    return Entry(
        seq=int(cursor.lastrowid or 0),
        on=on,
        actor=who,
        action=action.strip(),
        subject=subject.strip(),
        detail=detail.strip(),
    )


def entries(
    book: Book,
    subject: str | None = None,
    actor: str | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> tuple[Entry, ...]:
    """Every entry, oldest first, narrowed the four ways somebody asks."""
    narrow = narrowing().maybe("subject = ?", subject).maybe("actor = ?", actor)
    narrow.since("on_day", since).until("on_day", until)
    rows = book.query(
        f"SELECT seq, on_day, actor, action, subject, detail FROM entry{narrow.where} ORDER BY seq",
        narrow.values,
    )
    return tuple(_entry(row) for row in rows)


def about(book: Book, subject: str) -> tuple[Entry, ...]:
    """Everything ever done to one thing, oldest first."""
    return entries(book, subject=subject)


def actors(book: Book) -> tuple[str, ...]:
    """Everybody who has done anything, in name order."""
    rows = book.query("SELECT DISTINCT actor FROM entry ORDER BY actor")
    return tuple(as_text(row, "actor") for row in rows)


def unattributed(book: Book) -> int:
    """How many entries nobody put a name to."""
    return int(book.scalar("SELECT count(*) FROM entry WHERE actor = ?", (UNKNOWN,)) or 0)


def check_append_only(book: Book) -> None:
    """Prove the journal cannot be edited, by trying it.

    A positive control. A trigger that has never been fired is a trigger
    somebody believes in, and this is the difference between believing it
    and knowing.
    """
    try:
        book.execute("UPDATE entry SET detail = 'tidied' WHERE seq = (SELECT min(seq) FROM entry)")
    except ConflictError:
        return
    raise ConflictError("the journal took an update, so it is not append only")
