"""Reading and writing gradings.

A grading is three tables. The grading itself, the reasons it was rejected,
and the lines that came off an accepted load. They are separate tables
because a grading has none of one and several of the other, and because a
rejected load has neither adjustments nor a settled weight.

A grading is written once. There is no correcting a grading: a load that was
graded wrong is regraded by voiding this one and writing another, which is
`void_grading` here, and the void leaves a record that the office can see.
Editing the numbers under a settlement that has already been paid is the one
thing this book will not do.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from decimal import Decimal

from culmbin.errors import NotFoundError
from culmbin.intake.grading import Adjustment, Grading
from culmbin.model.enums import IntakeOutcome, RejectionReason
from culmbin.store.book import Book
from culmbin.store.rows import (
    as_enum,
    as_money,
    as_number,
    as_text,
    date_text,
    money_text,
)

_COLUMNS = "ticket, standard, outcome, net_tonnes, settled_tonnes, graded_on"


def _rejections(book: Book, ticket: str) -> tuple[RejectionReason, ...]:
    """The reasons a load went back, in the order of the enumeration."""
    rows = book.query("SELECT reason FROM rejection WHERE ticket = ?", (ticket,))
    held = {as_enum(row, "reason", RejectionReason) for row in rows}
    return tuple(reason for reason in RejectionReason if reason in held)


def _adjustments(book: Book, ticket: str) -> tuple[Adjustment, ...]:
    """The lines that came off a load, in the order they were worked."""
    rows = book.query(
        "SELECT kind, note, tonnes, per_tonne FROM adjustment WHERE ticket = ? ORDER BY seq",
        (ticket,),
    )
    return tuple(
        Adjustment(
            kind=as_text(row, "kind"),
            note=as_text(row, "note"),
            tonnes=as_number(row, "tonnes"),
            per_tonne=as_money(row, "per_tonne"),
        )
        for row in rows
    )


def _grading(book: Book, row: sqlite3.Row) -> Grading:
    """Turn a row and its two child tables into a grading."""
    ticket = as_text(row, "ticket")
    return Grading(
        ticket=ticket,
        standard=as_text(row, "standard"),
        outcome=as_enum(row, "outcome", IntakeOutcome),
        net_tonnes=as_number(row, "net_tonnes"),
        settled_tonnes=as_number(row, "settled_tonnes"),
        rejections=_rejections(book, ticket),
        adjustments=_adjustments(book, ticket),
    )


def save_grading(book: Book, grading: Grading, graded_on: dt.date) -> Grading:
    """Write a grading, its reasons and its lines, all together."""
    with book.writing() as writing:
        writing.execute(
            f"INSERT INTO grading ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
            (
                grading.ticket,
                grading.standard,
                grading.outcome,
                grading.net_tonnes,
                grading.settled_tonnes,
                date_text(graded_on),
            ),
        )
        writing.executemany(
            "INSERT INTO rejection (ticket, reason) VALUES (?, ?)",
            [(grading.ticket, reason) for reason in grading.rejections],
        )
        writing.executemany(
            "INSERT INTO adjustment (ticket, seq, kind, note, tonnes, per_tonne) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    grading.ticket,
                    seq,
                    line.kind,
                    line.note,
                    line.tonnes,
                    money_text(line.per_tonne),
                )
                for seq, line in enumerate(grading.adjustments, start=1)
            ],
        )
    return grading


def get_grading(book: Book, ticket: str) -> Grading:
    """One grading, or say which ticket was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM grading WHERE ticket = ?", (ticket,))
    if row is None:
        raise NotFoundError(f"ticket {ticket!r} has not been graded")
    return _grading(book, row)


def find_grading(book: Book, ticket: str) -> Grading | None:
    """One grading, or nothing."""
    try:
        return get_grading(book, ticket)
    except NotFoundError:
        return None


def graded_on(book: Book, ticket: str) -> dt.date:
    """The day a load was graded, which is not always the day it arrived."""
    row = book.first("SELECT graded_on FROM grading WHERE ticket = ?", (ticket,))
    if row is None:
        raise NotFoundError(f"ticket {ticket!r} has not been graded")
    return dt.date.fromisoformat(as_text(row, "graded_on"))


def void_grading(book: Book, ticket: str) -> None:
    """Take a grading off a load so it can be graded again.

    The reasons and the lines go with it, because they belong to the grading
    and not to the load. What is left is a delivery that has been sampled
    and not graded, which is exactly where it was before.
    """
    if find_grading(book, ticket) is None:
        raise NotFoundError(f"ticket {ticket!r} has not been graded")
    with book.writing() as writing:
        writing.execute("DELETE FROM adjustment WHERE ticket = ?", (ticket,))
        writing.execute("DELETE FROM rejection WHERE ticket = ?", (ticket,))
        writing.execute("DELETE FROM grading WHERE ticket = ?", (ticket,))


def regrade(book: Book, grading: Grading, graded_on_day: dt.date) -> Grading:
    """Replace a grading with another one.

    The two halves are in one transaction, so a load is never left with no
    grading at all because the second half failed.
    """
    with book.writing():
        void_grading(book, grading.ticket)
        return save_grading(book, grading, graded_on_day)


def list_gradings(
    book: Book,
    outcome: IntakeOutcome | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> tuple[Grading, ...]:
    """Every grading, oldest first, narrowed by outcome and by day."""
    clauses = []
    params: list[object] = []
    if outcome is not None:
        clauses.append("outcome = ?")
        params.append(outcome)
    if since is not None:
        clauses.append("graded_on >= ?")
        params.append(date_text(since))
    if until is not None:
        clauses.append("graded_on <= ?")
        params.append(date_text(until))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.query(f"SELECT {_COLUMNS} FROM grading{where} ORDER BY graded_on, ticket", params)
    return tuple(_grading(book, row) for row in rows)


def ungraded(book: Book, until: dt.date | None = None) -> tuple[str, ...]:
    """Every sampled delivery that has not been graded, oldest first.

    A load with a sample and no grading is one the lab has reported on and
    nobody has acted on, which is different from one that has not been
    sampled at all.
    """
    clauses = ["d.sample IS NOT NULL", "g.ticket IS NULL"]
    params: list[object] = []
    if until is not None:
        clauses.append("d.arrived <= ?")
        params.append(date_text(until))
    rows = book.query(
        "SELECT d.ticket FROM delivery d LEFT JOIN grading g ON g.ticket = d.ticket "
        f"WHERE {' AND '.join(clauses)} ORDER BY d.arrived, d.ticket",
        params,
    )
    return tuple(as_text(row, "ticket") for row in rows)


def rejected_count(book: Book, since: dt.date | None = None) -> int:
    """How many loads have gone back, for the intake summary."""
    if since is None:
        return int(book.scalar("SELECT count(*) FROM grading WHERE outcome = 'rejected'") or 0)
    return int(
        book.scalar(
            "SELECT count(*) FROM grading WHERE outcome = 'rejected' AND graded_on >= ?",
            (date_text(since),),
        )
        or 0
    )


def deduction_total(book: Book, ticket: str) -> Decimal:
    """Everything coming off the price of a settled tonne on one load."""
    return get_grading(book, ticket).price_adjustment
