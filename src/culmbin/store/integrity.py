"""Asking a book whether it still makes sense.

Every rule in this package is enforced where the writing happens, and none
of that helps a book that was edited in a `sqlite3` shell at half past six
on a Friday. This is the other end: given a book, what is wrong with it now.

Three sorts of question, and they are worth keeping apart.

**What SQLite itself says.** The integrity check and the foreign key check.
If either of these says anything, nothing below it is worth reading.

**What the schema could not say.** A CHECK constraint sees one row. Half the
rules in this package are about two tables at once, and those are here.

One of these was wrong for a fortnight and the walk in CI found it. It read
every shipment against an unsigned contract as a fault, and a contract that
has been served out and closed with despatched loads against it is not a
fault, it is what a finished contract looks like. Only a load still waiting
to go is one.

**What is merely odd.** A lot bigger than the bin it came out of is not
impossible, because the bin has been drawn since. It is worth a look and it
is not a fault, so it is reported separately and does not fail the command.
"""

from __future__ import annotations

from dataclasses import dataclass

from culmbin.store.book import Book


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing wrong with a book."""

    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.detail}"


def sqlite_says(book: Book) -> list[Finding]:
    """Whatever SQLite thinks is wrong with the file and its keys."""
    found = []
    for row in book.query("PRAGMA integrity_check"):
        message = str(row[0])
        if message != "ok":
            found.append(Finding("integrity", message))
    for row in book.query("PRAGMA foreign_key_check"):
        found.append(Finding("foreign key", f"{row[0]} row {row[1]} refers to a missing {row[2]}"))
    return found


def _rows(book: Book, kind: str, detail: str, sql: str) -> list[Finding]:
    """Every row a question turns up, as findings."""
    return [
        Finding(kind, detail.format(**dict(zip(row.keys(), tuple(row), strict=True))))
        for row in book.query(sql)
    ]


def crossing_rules(book: Book) -> list[Finding]:
    """Everything a CHECK constraint could not see, because it spans two tables."""
    found = []
    found += _rows(
        book,
        "grading",
        "{ticket} has been graded and has no sample against it",
        "SELECT g.ticket FROM grading g JOIN delivery d ON d.ticket = g.ticket "
        "WHERE d.sample IS NULL",
    )
    found += _rows(
        book,
        "silo",
        "{ticket} was rejected and is in a silo",
        "SELECT r.ticket FROM silo_receipt r JOIN grading g ON g.ticket = r.ticket "
        "WHERE g.outcome = 'rejected'",
    )
    found += _rows(
        book,
        "shipment",
        "{code} is waiting to go against {contract}, which is not signed",
        "SELECT s.code, s.contract FROM shipment s JOIN contract c ON c.code = s.contract "
        "WHERE c.state != 'signed' AND s.state IN ('planned', 'loaded')",
    )
    found += _rows(
        book,
        "lot",
        "{code} has no analysis and has been shipped",
        "SELECT l.code FROM malt_lot l JOIN shipment s ON s.lot = l.code "
        "WHERE l.analysis IS NULL AND s.state != 'cancelled'",
    )
    found += _rows(
        book,
        "piece",
        "{code} is in {vessel} and so is something else",
        "SELECT p.code, p.vessel FROM piece p WHERE p.vessel IS NOT NULL AND ("
        "  SELECT count(*) FROM piece q WHERE q.vessel = p.vessel"
        ") > 1",
    )
    found += _rows(
        book,
        "source",
        "{piece} was charged with more off {ticket} than the silo ever had",
        "SELECT s.piece, s.ticket FROM piece_source s "
        "JOIN silo_receipt r ON r.ticket = s.ticket "
        "GROUP BY s.piece, s.ticket HAVING total(s.tonnes) > r.tonnes + 0.001",
    )
    return found


def worth_a_look(book: Book) -> list[Finding]:
    """Everything odd but not wrong, which does not fail the command."""
    found = []
    found += _rows(
        book,
        "lot",
        "{code} was sealed at more than {malt_bin} holds today",
        "SELECT l.code, l.malt_bin FROM malt_lot l JOIN malt_bin b ON b.code = l.malt_bin "
        "WHERE l.tonnes > b.capacity_tonnes",
    )
    found += _rows(
        book,
        "piece",
        "{code} has no lorry loads recorded against it",
        "SELECT p.code FROM piece p LEFT JOIN piece_source s ON s.piece = p.code "
        "WHERE s.piece IS NULL",
    )
    found += _rows(
        book,
        "delivery",
        "{ticket} was graded and never tipped into a silo",
        "SELECT d.ticket FROM delivery d JOIN grading g ON g.ticket = d.ticket "
        "LEFT JOIN silo_receipt r ON r.ticket = d.ticket "
        "WHERE g.outcome != 'rejected' AND r.ticket IS NULL",
    )
    return found


def faults(book: Book) -> list[Finding]:
    """Everything that is actually wrong, worst first.

    SQLite's own findings come first because nothing below them is worth
    reading until they are dealt with.
    """
    first = sqlite_says(book)
    return first if first else crossing_rules(book)


def sound(book: Book) -> bool:
    """Whether a book has anything wrong with it."""
    return not faults(book)


def tables_holding_nothing(book: Book) -> tuple[str, ...]:
    """Every table with no rows in it, in name order.

    Not a fault and often not even odd. It is here because it is the first
    thing anybody wants after restoring a backup: which parts of the book
    came back empty.
    """
    return tuple(table for table in book.tables() if book.row_count(table) == 0)


def summary(book: Book) -> tuple[int, int, int]:
    """How many faults, how many oddities, and how many tables hold nothing."""
    return len(faults(book)), len(worth_a_look(book)), len(tables_holding_nothing(book))
