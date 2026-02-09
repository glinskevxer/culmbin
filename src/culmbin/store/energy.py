"""Reading and writing what the gas meter did across a kiln run.

A run is only worth recording once the piece has been stripped, because
half the arithmetic needs the weight that came off the kiln. So this refuses
a piece that has not been weighed at both ends rather than storing a meter
reading nothing can be done with.

The efficiency is not stored. It is three measured numbers and a constant,
and a stored fourth number that has to agree with them is a number that
eventually will not.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import NotFoundError, StateError
from culmbin.process.energy import KilnEnergy
from culmbin.store.book import Book
from culmbin.store.pieces import find_piece, weighings
from culmbin.store.query import narrowing, optional
from culmbin.store.rows import as_number, as_text, date_text

_COLUMNS = "piece, kiln, gas_m3, on_day, note"


def _run(book: Book, row: sqlite3.Row) -> KilnEnergy:
    """Turn a row and the piece's weights into a kiln run."""
    piece = as_text(row, "piece")
    weights = weighings(book, piece)
    steep_out, green_moisture = weights["steep_out"]
    malt, malt_moisture = weights["off_kiln"]
    assert green_moisture is not None
    assert malt_moisture is not None
    return KilnEnergy(
        piece=piece,
        green_tonnes=steep_out,
        green_moisture=green_moisture,
        malt_tonnes=malt,
        malt_moisture=malt_moisture,
        gas_m3=as_number(row, "gas_m3"),
    )


def record_run(
    book: Book, piece: str, kiln: str, gas_m3: float, on: dt.date, note: str = ""
) -> KilnEnergy:
    """Write what the meter read across one piece's time on a kiln."""
    if find_piece(book, piece) is None:
        raise NotFoundError(f"no piece called {piece!r}")
    weights = weighings(book, piece)
    missing = [point for point in ("steep_out", "off_kiln") if point not in weights]
    if missing:
        raise StateError(
            f"{piece} has not been weighed at {', '.join(missing)}, so a meter reading says nothing"
        )
    book.execute(
        f"INSERT INTO kiln_run ({_COLUMNS}) VALUES (?, ?, ?, ?, ?)",
        (piece, kiln, gas_m3, date_text(on), note),
    )
    return get_run(book, piece)


def get_run(book: Book, piece: str) -> KilnEnergy:
    """One kiln run, or say which piece was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM kiln_run WHERE piece = ?", (piece,))
    if row is None:
        raise NotFoundError(f"no kiln run recorded against {piece!r}")
    return _run(book, row)


def find_run(book: Book, piece: str) -> KilnEnergy | None:
    """One kiln run, or nothing."""
    return optional(lambda: get_run(book, piece))


def kiln_of(book: Book, piece: str) -> str:
    """Which kiln a run was on."""
    row = book.first("SELECT kiln FROM kiln_run WHERE piece = ?", (piece,))
    if row is None:
        raise NotFoundError(f"no kiln run recorded against {piece!r}")
    return as_text(row, "kiln")


def list_runs(
    book: Book,
    kiln: str | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> tuple[KilnEnergy, ...]:
    """Every kiln run, oldest first, narrowed by kiln and by day."""
    narrow = narrowing().maybe("kiln = ?", kiln)
    narrow.since("on_day", since).until("on_day", until)
    rows = book.query(
        f"SELECT {_COLUMNS} FROM kiln_run{narrow.where} ORDER BY on_day, piece", narrow.values
    )
    return tuple(_run(book, row) for row in rows)


def unmetered(book: Book) -> tuple[str, ...]:
    """Every stripped piece with no meter reading against it, oldest first.

    A month with half its runs unmetered has a gas figure that cannot be
    compared with anything, so the list matters more than it looks.
    """
    rows = book.query(
        "SELECT p.code FROM piece p "
        "JOIN weighing w ON w.piece = p.code AND w.point = 'off_kiln' "
        "LEFT JOIN kiln_run r ON r.piece = p.code "
        "WHERE r.piece IS NULL ORDER BY p.started, p.code"
    )
    return tuple(as_text(row, "code") for row in rows)


def gas_used(book: Book, since: dt.date | None = None, until: dt.date | None = None) -> float:
    """Cubic metres burnt over a stretch of days, off the meter readings."""
    narrow = narrowing().since("on_day", since).until("on_day", until)
    total = book.scalar(f"SELECT total(gas_m3) FROM kiln_run{narrow.where}", narrow.values)
    return float(total or 0.0)


def suspect_runs(book: Book) -> tuple[KilnEnergy, ...]:
    """Every run whose efficiency is outside what a kiln can do.

    Somebody should look before the figure goes on a monthly report, because
    one run at two hundred percent moves a month's average further than any
    real improvement ever will.
    """
    return tuple(run for run in list_runs(book) if run.gas_m3 > 0.0 and run.suspect)
