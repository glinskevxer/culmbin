"""Reading and writing barley silos.

There is no table of draws. A draw out of a silo *is* the set of
`piece_source` rows it writes, so the tonnage left of each load is the
tonnage that went in less everything charged off it, and the two can never
disagree because there is only one of them.

That is the same decision as the malt bins, from the other end: what is in a
silo is worked out and never stored. The one thing stored is the mixed mark,
because a silo drawn to nothing still has a tonne under the sweep auger and
no arithmetic over the movements can know that.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import IntakeOutcome
from culmbin.model.silo import Holding, Silo, holding_of
from culmbin.store.book import Book
from culmbin.store.query import optional
from culmbin.store.rows import (
    as_count,
    as_number,
    as_optional_date,
    as_text,
    date_text,
    optional_date_text,
)

_COLUMNS = "code, capacity_tonnes, mixed, commissioned"


def _silo(row: sqlite3.Row) -> Silo:
    """Turn a row into a silo."""
    return Silo(
        code=as_text(row, "code"),
        capacity_tonnes=as_number(row, "capacity_tonnes"),
        mixed=bool(as_count(row, "mixed")),
        commissioned=as_optional_date(row, "commissioned"),
    )


def add_silo(book: Book, silo: Silo) -> Silo:
    """Write a new silo."""
    book.execute(
        f"INSERT INTO silo ({_COLUMNS}) VALUES (?, ?, ?, ?)",
        (
            silo.code,
            silo.capacity_tonnes,
            int(silo.mixed),
            optional_date_text(silo.commissioned),
        ),
    )
    return silo


def get_silo(book: Book, code: str) -> Silo:
    """One silo, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM silo WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no silo called {code!r}")
    return _silo(row)


def find_silo(book: Book, code: str) -> Silo | None:
    """One silo, or nothing."""
    return optional(lambda: get_silo(book, code))


def list_silos(book: Book) -> tuple[Silo, ...]:
    """Every silo, in code order."""
    return tuple(_silo(row) for row in book.query(f"SELECT {_COLUMNS} FROM silo ORDER BY code"))


def _write_silo(book: Book, silo: Silo) -> Silo:
    """Write a silo that is already there."""
    book.execute(
        "UPDATE silo SET capacity_tonnes = ?, mixed = ?, commissioned = ? WHERE code = ?",
        (
            silo.capacity_tonnes,
            int(silo.mixed),
            optional_date_text(silo.commissioned),
            silo.code,
        ),
    )
    return silo


def holding_in(book: Book, code: str) -> Holding:
    """What is in a silo, worked off the loads in and the pieces out."""
    if find_silo(book, code) is None:
        raise NotFoundError(f"no silo called {code!r}")
    rows = book.query(
        "SELECT r.ticket, r.tonnes, r.moisture, p.variety, p.crop_year "
        "FROM silo_receipt r "
        "JOIN delivery d ON d.ticket = r.ticket "
        "JOIN purchase p ON p.code = d.purchase "
        "WHERE r.silo = ? ORDER BY r.on_day, r.ticket",
        (code,),
    )
    parts = []
    varieties = []
    crop_years = []
    for row in rows:
        ticket = as_text(row, "ticket")
        drawn = float(
            book.scalar("SELECT total(tonnes) FROM piece_source WHERE ticket = ?", (ticket,)) or 0.0
        )
        left = as_number(row, "tonnes") - drawn
        varieties.append(as_text(row, "variety"))
        crop_years.append(as_count(row, "crop_year"))
        if left > 1e-9:
            parts.append((ticket, left, as_number(row, "moisture")))
    return holding_of(code, parts, varieties, crop_years)


def tip(book: Book, code: str, ticket: str, on: dt.date) -> Silo:
    """Tip an accepted load into a silo.

    The tonnage that goes in is the *settled* tonnage, not the weighbridge
    net. The screenings went in a different bin and the water is not barley,
    so putting the lorry weight into the silo would overstate it by whatever
    the grading took off.
    """
    silo = get_silo(book, code)
    row = book.first(
        "SELECT g.outcome, g.settled_tonnes, a.value AS moisture "
        "FROM grading g "
        "JOIN delivery d ON d.ticket = g.ticket "
        "LEFT JOIN result a ON a.analysis = d.sample AND a.code = 'moisture' "
        "WHERE g.ticket = ?",
        (ticket,),
    )
    if row is None:
        raise StateError(f"ticket {ticket} has not been graded, so nothing can be tipped")
    if as_text(row, "outcome") == IntakeOutcome.REJECTED.value:
        raise StateError(f"ticket {ticket} was rejected and went back down the road")
    tonnes = as_number(row, "settled_tonnes")
    held = holding_in(book, code)
    if held.tonnes + tonnes > silo.capacity_tonnes + 1e-9:
        raise ConflictError(
            f"{tonnes:.2f}t into {code} would make {held.tonnes + tonnes:.2f}t "
            f"against a capacity of {silo.capacity_tonnes:.0f}t"
        )
    variety = book.one(
        "SELECT p.variety FROM delivery d JOIN purchase p ON p.code = d.purchase "
        "WHERE d.ticket = ?",
        (ticket,),
        what="delivery",
    )
    mixes = bool(held.varieties) and as_text(variety, "variety") not in held.varieties
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO silo_receipt (silo, ticket, tonnes, moisture, on_day) "
            "VALUES (?, ?, ?, ?, ?)",
            (code, ticket, tonnes, as_number(row, "moisture"), date_text(on)),
        )
        if mixes:
            _write_silo(book, silo.marked_mixed())
    return get_silo(book, code)


def sweep(book: Book, code: str) -> Silo:
    """Take the mixed mark off a silo that has been emptied and swept out."""
    silo = get_silo(book, code)
    if not holding_in(book, code).empty:
        raise StateError(f"{code} still has barley in it and cannot be swept")
    return _write_silo(book, silo.swept())


def silo_holding(book: Book, ticket: str) -> str | None:
    """Which silo a lorry load went into, or nothing if it has not been tipped."""
    row = book.first("SELECT silo FROM silo_receipt WHERE ticket = ?", (ticket,))
    return None if row is None else as_text(row, "silo")


def untipped(book: Book) -> tuple[str, ...]:
    """Every accepted load that has not been put anywhere, oldest first.

    A load that has been graded and not tipped is barley in the intake pit,
    and the pit is where it goes bad.
    """
    rows = book.query(
        "SELECT d.ticket FROM delivery d "
        "JOIN grading g ON g.ticket = d.ticket "
        "LEFT JOIN silo_receipt r ON r.ticket = d.ticket "
        "WHERE g.outcome != 'rejected' AND r.ticket IS NULL "
        "ORDER BY d.arrived, d.ticket"
    )
    return tuple(as_text(row, "ticket") for row in rows)
