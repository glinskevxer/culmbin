"""Reading and writing malt bins, and working out what is in one.

What is in a bin is not stored. It is worked out of the receipts and the
issues every time it is asked for, because a stored figure and a movement
history that disagree is a question nobody can settle, and they always
eventually disagree.

The one thing that *is* stored is the mixed mark, and that is because it is
not derivable. A bin drawn to nothing and refilled from one piece has one
variety in its movement history since it was last empty, and it still has
last month's variety in the boot. The mark survives the bin going empty and
comes off when somebody has cleaned it out.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import BinState, MaltStyle
from culmbin.model.lots import Bin, Contents
from culmbin.store.book import Book
from culmbin.store.pieces import get_piece
from culmbin.store.rows import (
    as_count,
    as_enum,
    as_number,
    as_optional_date,
    as_text,
    date_text,
    optional_date_text,
)
from culmbin.units.mass import blend_moisture

_COLUMNS = "code, capacity_tonnes, state, mixed, commissioned"


def _bin(row: sqlite3.Row) -> Bin:
    """Turn a row into a bin."""
    return Bin(
        code=as_text(row, "code"),
        capacity_tonnes=as_number(row, "capacity_tonnes"),
        state=as_enum(row, "state", BinState),
        mixed=bool(as_count(row, "mixed")),
        commissioned=as_optional_date(row, "commissioned"),
    )


def add_bin(book: Book, malt_bin: Bin) -> Bin:
    """Write a new bin."""
    book.execute(
        f"INSERT INTO malt_bin ({_COLUMNS}) VALUES (?, ?, ?, ?, ?)",
        (
            malt_bin.code,
            malt_bin.capacity_tonnes,
            malt_bin.state,
            int(malt_bin.mixed),
            optional_date_text(malt_bin.commissioned),
        ),
    )
    return malt_bin


def get_bin(book: Book, code: str) -> Bin:
    """One bin, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM malt_bin WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no bin called {code!r}")
    return _bin(row)


def find_bin(book: Book, code: str) -> Bin | None:
    """One bin, or nothing."""
    try:
        return get_bin(book, code)
    except NotFoundError:
        return None


def list_bins(book: Book, state: BinState | None = None) -> tuple[Bin, ...]:
    """Every bin, in code order, optionally in one state."""
    if state is None:
        rows = book.query(f"SELECT {_COLUMNS} FROM malt_bin ORDER BY code")
    else:
        rows = book.query(
            f"SELECT {_COLUMNS} FROM malt_bin WHERE state = ? ORDER BY code", (state,)
        )
    return tuple(_bin(row) for row in rows)


def _write_bin(book: Book, malt_bin: Bin) -> Bin:
    """Write a bin that is already there."""
    book.execute(
        "UPDATE malt_bin SET capacity_tonnes = ?, state = ?, mixed = ?, commissioned = ? "
        "WHERE code = ?",
        (
            malt_bin.capacity_tonnes,
            malt_bin.state,
            int(malt_bin.mixed),
            optional_date_text(malt_bin.commissioned),
            malt_bin.code,
        ),
    )
    return malt_bin


def contents_of(book: Book, code: str) -> Contents:
    """What is in a bin, worked from what went in and what came out."""
    if find_bin(book, code) is None:
        raise NotFoundError(f"no bin called {code!r}")
    receipts = book.query(
        "SELECT r.tonnes, r.moisture, p.variety, p.crop_year, p.style "
        "FROM bin_receipt r JOIN piece p ON p.code = r.piece "
        "WHERE r.malt_bin = ? ORDER BY r.seq",
        (code,),
    )
    issued = float(
        book.scalar("SELECT total(tonnes) FROM bin_issue WHERE malt_bin = ?", (code,)) or 0.0
    )
    if not receipts:
        return Contents(code=code, tonnes=0.0, moisture=0.0)
    received = sum(as_number(row, "tonnes") for row in receipts)
    return Contents(
        code=code,
        tonnes=max(0.0, received - issued),
        moisture=blend_moisture(
            [(as_number(row, "tonnes"), as_number(row, "moisture")) for row in receipts]
        ),
        varieties=frozenset(as_text(row, "variety") for row in receipts),
        crop_years=frozenset(as_count(row, "crop_year") for row in receipts),
        styles=frozenset(as_enum(row, "style", MaltStyle) for row in receipts),
    )


def receive(book: Book, code: str, piece: str, tonnes: float, moisture: float, on: dt.date) -> Bin:
    """Tip a piece of malt into a bin.

    Marks the bin mixed if what is going in is a different variety from what
    is already there. The mark is on the bin and not on the receipt, because
    the next thing to go in has to know about it.
    """
    malt_bin = get_bin(book, code)
    if not malt_bin.takes_malt:
        raise StateError(f"{code} is {malt_bin.state} and takes nothing")
    if tonnes <= 0.0:
        raise ConflictError(f"a receipt of {tonnes} tonnes is not a receipt")
    held = contents_of(book, code)
    if held.tonnes + tonnes > malt_bin.capacity_tonnes + 1e-9:
        raise ConflictError(
            f"{tonnes:.1f}t into {code} would make {held.tonnes + tonnes:.1f}t "
            f"against a capacity of {malt_bin.capacity_tonnes:.1f}t"
        )
    tipping = get_piece(book, piece)
    mixes = bool(held.varieties) and tipping.variety not in held.varieties
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO bin_receipt (malt_bin, seq, piece, tonnes, moisture, on_day) "
            "VALUES (?, (SELECT count(*) + 1 FROM bin_receipt WHERE malt_bin = ?), ?, ?, ?, ?)",
            (code, code, piece, tonnes, moisture, date_text(on)),
        )
        updated = malt_bin.in_state(BinState.FILLING)
        if mixes:
            updated = updated.marked_mixed()
        _write_bin(book, updated)
    return get_bin(book, code)


def issue(book: Book, code: str, tonnes: float, on: dt.date, note: str = "") -> Bin:
    """Draw malt out of a bin.

    A bin drawn to nothing goes back to empty and keeps its mixed mark,
    which is the whole point of the mark.
    """
    malt_bin = get_bin(book, code)
    if not malt_bin.gives_malt:
        raise StateError(f"{code} is {malt_bin.state} and gives nothing")
    held = contents_of(book, code)
    if tonnes <= 0.0:
        raise ConflictError(f"an issue of {tonnes} tonnes is not an issue")
    if tonnes > held.tonnes + 1e-9:
        raise ConflictError(f"{code} holds {held.tonnes:.1f}t and {tonnes:.1f}t was asked for")
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO bin_issue (malt_bin, seq, tonnes, on_day, note) "
            "VALUES (?, (SELECT count(*) + 1 FROM bin_issue WHERE malt_bin = ?), ?, ?, ?)",
            (code, code, tonnes, date_text(on), note),
        )
        left = held.tonnes - tonnes
        state = BinState.EMPTY if left <= 1e-9 else BinState.DRAWING
        _write_bin(book, malt_bin.in_state(state))
    return get_bin(book, code)


def seal(book: Book, code: str) -> Bin:
    """Seal a bin so nothing else can go in and a lot can be drawn from it."""
    malt_bin = get_bin(book, code)
    if malt_bin.state is not BinState.FILLING:
        raise StateError(f"{code} is {malt_bin.state} and only a filling bin is sealed")
    if contents_of(book, code).empty:
        raise StateError(f"{code} has nothing in it to seal")
    return _write_bin(book, malt_bin.in_state(BinState.SEALED))


def clean_out(book: Book, code: str) -> Bin:
    """Take the mixed mark off a bin that has been emptied and swept."""
    malt_bin = get_bin(book, code)
    return _write_bin(book, malt_bin.cleaned_out())


def receipts_of(book: Book, code: str) -> tuple[tuple[str, float, float, dt.date], ...]:
    """Every piece that has gone into a bin, in the order it went."""
    rows = book.query(
        "SELECT piece, tonnes, moisture, on_day FROM bin_receipt WHERE malt_bin = ? ORDER BY seq",
        (code,),
    )
    return tuple(
        (
            as_text(row, "piece"),
            as_number(row, "tonnes"),
            as_number(row, "moisture"),
            dt.date.fromisoformat(as_text(row, "on_day")),
        )
        for row in rows
    )


def bins_holding(book: Book, piece: str) -> tuple[str, ...]:
    """Every bin a piece has gone into, in code order.

    A piece can be split across bins when it does not fit in one, so this
    answers with a list rather than with a bin.
    """
    rows = book.query(
        "SELECT DISTINCT malt_bin FROM bin_receipt WHERE piece = ? ORDER BY malt_bin", (piece,)
    )
    return tuple(as_text(row, "malt_bin") for row in rows)
