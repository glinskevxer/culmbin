"""Sealing a lot out of a bin, and reading one back.

A lot is a photograph. It is what was in a bin at the moment somebody sealed
it and took a sample, and it does not move afterwards even though the bin
does. Malt is drawn out of the bin against the lot, the bin empties, and the
lot still says what it said, because the certificate that went to the
customer says the same thing.

That is why the varieties, the crop years and the parent pieces are copied
onto the lot rather than looked up through the bin. Six months later the bin
has held three other things, and the question being asked is about the lot.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import BinState, MaltStyle
from culmbin.model.lots import MaltLot
from culmbin.store.bins import contents_of, get_bin
from culmbin.store.book import Book
from culmbin.store.rows import (
    as_count,
    as_date,
    as_number,
    as_optional_text,
    as_text,
    date_text,
)


def _lot(book: Book, row: sqlite3.Row) -> MaltLot:
    """Turn a row and its three child tables into a lot."""
    code = as_text(row, "code")
    varieties = book.query(
        "SELECT variety FROM lot_variety WHERE lot = ? ORDER BY variety", (code,)
    )
    years = book.query(
        "SELECT crop_year FROM lot_crop_year WHERE lot = ? ORDER BY crop_year", (code,)
    )
    parents = book.query("SELECT piece FROM lot_parent WHERE lot = ? ORDER BY piece", (code,))
    style = as_optional_text(row, "style")
    return MaltLot(
        code=code,
        bin_code=as_text(row, "malt_bin"),
        sealed=as_date(row, "sealed"),
        tonnes=as_number(row, "tonnes"),
        moisture=as_number(row, "moisture"),
        analysis=as_optional_text(row, "analysis"),
        varieties=frozenset(as_text(item, "variety") for item in varieties),
        crop_years=frozenset(as_count(item, "crop_year") for item in years),
        style=None if style is None else MaltStyle(style),
        parents=tuple(as_text(item, "piece") for item in parents),
    )


def seal_lot(book: Book, code: str, malt_bin: str, on: dt.date) -> MaltLot:
    """Take a lot out of a sealed bin, copying everything it needs off it.

    The bin has to be sealed first. A lot off a bin that is still filling is
    a lot whose analysis describes something that is not there any more by
    the time the certificate is printed.
    """
    held_bin = get_bin(book, malt_bin)
    if held_bin.state is not BinState.SEALED:
        raise StateError(f"{malt_bin} is {held_bin.state} and a lot comes off a sealed bin")
    held = contents_of(book, malt_bin)
    if held.empty:
        raise StateError(f"{malt_bin} has nothing in it")
    pieces = book.query(
        "SELECT DISTINCT piece FROM bin_receipt WHERE malt_bin = ? ORDER BY piece", (malt_bin,)
    )
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO malt_lot (code, malt_bin, sealed, tonnes, moisture, style) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                code,
                malt_bin,
                date_text(on),
                held.tonnes,
                held.moisture,
                held.style,
            ),
        )
        writing.executemany(
            "INSERT INTO lot_variety (lot, variety) VALUES (?, ?)",
            [(code, variety) for variety in sorted(held.varieties)],
        )
        writing.executemany(
            "INSERT INTO lot_crop_year (lot, crop_year) VALUES (?, ?)",
            [(code, year) for year in sorted(held.crop_years)],
        )
        writing.executemany(
            "INSERT INTO lot_parent (lot, piece) VALUES (?, ?)",
            [(code, as_text(row, "piece")) for row in pieces],
        )
    return get_lot(book, code)


def get_lot(book: Book, code: str) -> MaltLot:
    """One lot, or say which one was asked for."""
    row = book.first(
        "SELECT code, malt_bin, sealed, tonnes, moisture, analysis, style "
        "FROM malt_lot WHERE code = ?",
        (code,),
    )
    if row is None:
        raise NotFoundError(f"no lot called {code!r}")
    return _lot(book, row)


def find_lot(book: Book, code: str) -> MaltLot | None:
    """One lot, or nothing."""
    try:
        return get_lot(book, code)
    except NotFoundError:
        return None


def certify(book: Book, code: str, analysis: str) -> MaltLot:
    """Put an analysis against a lot.

    Refuses to move one. A second analysis of the same lot is a retest, and
    a retest gets its own reference and its own certificate rather than
    quietly replacing the numbers that were already sent out.
    """
    lot = get_lot(book, code)
    if lot.certified:
        raise ConflictError(f"{code} was already certified as {lot.analysis}")
    book.execute("UPDATE malt_lot SET analysis = ? WHERE code = ?", (analysis, code))
    return get_lot(book, code)


def list_lots(
    book: Book,
    variety: str | None = None,
    style: MaltStyle | None = None,
    certified: bool | None = None,
) -> tuple[MaltLot, ...]:
    """Every lot, newest last, narrowed the three ways the sales desk asks.

    Filtering by variety means lots that can be *sold* as that variety, so a
    mixed lot that happens to contain it is not on the list. That is the
    segregation rule, applied where it is asked rather than afterwards.
    """
    clauses = []
    params: list[object] = []
    if style is not None:
        clauses.append("style = ?")
        params.append(style)
    if certified is True:
        clauses.append("analysis IS NOT NULL")
    if certified is False:
        clauses.append("analysis IS NULL")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.query(
        "SELECT code, malt_bin, sealed, tonnes, moisture, analysis, style "
        f"FROM malt_lot{where} ORDER BY sealed, code",
        params,
    )
    lots = tuple(_lot(book, row) for row in rows)
    if variety is None:
        return lots
    return tuple(lot for lot in lots if lot.serves(variety))


def lots_from_piece(book: Book, piece: str) -> tuple[MaltLot, ...]:
    """Every lot a piece ended up in, in code order.

    This is the forward half of the traceability walk: a piece went wrong,
    and the question is where it went.
    """
    rows = book.query(
        "SELECT l.code, l.malt_bin, l.sealed, l.tonnes, l.moisture, l.analysis, l.style "
        "FROM malt_lot l JOIN lot_parent p ON p.lot = l.code "
        "WHERE p.piece = ? ORDER BY l.code",
        (piece,),
    )
    return tuple(_lot(book, row) for row in rows)


def uncertified(book: Book) -> tuple[MaltLot, ...]:
    """Every sealed lot with no analysis against it, oldest first.

    This is the laboratory's queue. A lot with no certificate cannot be
    shipped, so a long list here is malt in bins that cannot be sold.
    """
    return list_lots(book, certified=False)
