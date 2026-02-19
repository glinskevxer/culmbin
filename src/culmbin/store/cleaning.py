"""When a vessel was last cleaned, and whether it is overdue.

A steep that has not been cleaned smells, and a box that has not been
cleaned grows things that end up in somebody's beer. Every vessel therefore
has an interval, and it has two halves.

**Days and pieces, and whichever comes first.** A box run flat out for a
fortnight is due on pieces. The same box standing idle over Christmas is due
on days, and it is due for a different reason: what is growing in it while
nothing is happening is exactly the problem.

Being overdue does not stop a piece going in, and it is not silent either.
The floor can charge an overdue vessel and has to say why, and the reason
goes in the book next to the charge. That is deliberate: the alternative is
somebody backdating a cleaning record to get on with the day.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from culmbin.errors import ConflictError, NotFoundError
from culmbin.store.book import Book
from culmbin.store.query import optional
from culmbin.store.rows import as_count, as_date, as_text, date_text
from culmbin.store.vessels import get_vessel, list_vessels

DEFAULT_DAYS = 30
DEFAULT_PIECES = 12


@dataclass(frozen=True, slots=True)
class Interval:
    """How often a vessel has to be cleaned, both ways."""

    vessel: str
    days: int
    pieces: int

    def __post_init__(self) -> None:
        if self.days <= 0 or self.pieces <= 0:
            raise ConflictError(f"{self.vessel} cannot be cleaned every {self.days} days")


@dataclass(frozen=True, slots=True)
class Standing:
    """Where a vessel stands against its cleaning interval."""

    vessel: str
    interval: Interval
    last_cleaned: dt.date | None
    pieces_since: int

    @property
    def never_cleaned(self) -> bool:
        """Whether there is no cleaning record against this vessel at all."""
        return self.last_cleaned is None

    def days_since(self, on: dt.date) -> int | None:
        """How long since it was cleaned, or nothing if it never was."""
        if self.last_cleaned is None:
            return None
        return max(0, (on - self.last_cleaned).days)

    def overdue(self, on: dt.date) -> bool:
        """Whether it is past either half of its interval."""
        if self.last_cleaned is None:
            return True
        days = self.days_since(on)
        assert days is not None
        return days >= self.interval.days or self.pieces_since >= self.interval.pieces

    def why(self, on: dt.date) -> str:
        """A sentence saying which half it is overdue on, or that it is not."""
        if self.last_cleaned is None:
            return f"{self.vessel} has never been cleaned"
        days = self.days_since(on)
        assert days is not None
        reasons = []
        if days >= self.interval.days:
            reasons.append(f"{days} days against {self.interval.days}")
        if self.pieces_since >= self.interval.pieces:
            reasons.append(f"{self.pieces_since} pieces against {self.interval.pieces}")
        if not reasons:
            return f"{self.vessel} is inside its interval"
        return f"{self.vessel} is overdue on {' and '.join(reasons)}"


def set_interval(book: Book, vessel: str, days: int, pieces: int) -> Interval:
    """Say how often a vessel has to be cleaned."""
    get_vessel(book, vessel)
    interval = Interval(vessel, days, pieces)
    book.execute(
        "INSERT INTO cleaning_interval (vessel, days, pieces) VALUES (?, ?, ?) "
        "ON CONFLICT (vessel) DO UPDATE SET days = excluded.days, pieces = excluded.pieces",
        (vessel, days, pieces),
    )
    return interval


def interval_for(book: Book, vessel: str) -> Interval:
    """A vessel's interval, or the plant default if nobody has set one."""
    row = book.first("SELECT days, pieces FROM cleaning_interval WHERE vessel = ?", (vessel,))
    if row is None:
        return Interval(vessel, DEFAULT_DAYS, DEFAULT_PIECES)
    return Interval(vessel, as_count(row, "days"), as_count(row, "pieces"))


def record_cleaning(book: Book, vessel: str, on: dt.date, by_whom: str, note: str = "") -> dt.date:
    """Write down that a vessel was cleaned."""
    get_vessel(book, vessel)
    book.execute(
        "INSERT INTO cleaning (vessel, seq, on_day, by_whom, note) "
        "VALUES (?, (SELECT count(*) + 1 FROM cleaning WHERE vessel = ?), ?, ?, ?)",
        (vessel, vessel, date_text(on), by_whom, note),
    )
    return on


def last_cleaned(book: Book, vessel: str) -> dt.date | None:
    """When a vessel was last cleaned, or nothing."""
    row = book.first("SELECT max(on_day) AS on_day FROM cleaning WHERE vessel = ?", (vessel,))
    if row is None or row["on_day"] is None:
        return None
    return as_date(row, "on_day")


def cleanings(book: Book, vessel: str) -> tuple[tuple[dt.date, str, str], ...]:
    """Every cleaning of a vessel, oldest first."""
    rows = book.query(
        "SELECT on_day, by_whom, note FROM cleaning WHERE vessel = ? ORDER BY seq", (vessel,)
    )
    return tuple(
        (as_date(row, "on_day"), as_text(row, "by_whom"), as_text(row, "note")) for row in rows
    )


def pieces_since_cleaning(book: Book, vessel: str) -> int:
    """How many pieces have been through a vessel since it was cleaned."""
    cleaned = last_cleaned(book, vessel)
    if cleaned is None:
        total = book.scalar("SELECT count(*) FROM movement WHERE vessel = ?", (vessel,))
        return int(total or 0)
    total = book.scalar(
        "SELECT count(*) FROM movement WHERE vessel = ? AND on_day >= ?",
        (vessel, date_text(cleaned)),
    )
    return int(total or 0)


def standing(book: Book, vessel: str) -> Standing:
    """Where a vessel stands against its interval."""
    if optional(lambda: get_vessel(book, vessel)) is None:
        raise NotFoundError(f"no vessel called {vessel!r}")
    return Standing(
        vessel=vessel,
        interval=interval_for(book, vessel),
        last_cleaned=last_cleaned(book, vessel),
        pieces_since=pieces_since_cleaning(book, vessel),
    )


def overdue(book: Book, on: dt.date) -> tuple[Standing, ...]:
    """Every vessel past either half of its interval, in code order."""
    return tuple(
        found for vessel in list_vessels(book) if (found := standing(book, vessel.code)).overdue(on)
    )
