"""Reading and writing what the water meter did across a steep.

Recorded once the piece has been cast, because the arithmetic needs the
steep-out moisture, and once it has been stripped for the specific figure,
because that is per tonne of malt. So a reading goes in as soon as the
piece is cast and the figures that need the malt weight come back only when
there is one.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import NotFoundError, StateError
from culmbin.process.water import WaterUse
from culmbin.store.book import Book
from culmbin.store.pieces import get_piece, weighings
from culmbin.store.query import narrowing, optional
from culmbin.store.rows import as_number, as_text, date_text

_COLUMNS = "piece, metered_m3, on_day, note"


def _use(book: Book, row: sqlite3.Row) -> WaterUse:
    """Turn a row and the piece's weights into a water use."""
    code = as_text(row, "piece")
    piece = get_piece(book, code)
    weights = weighings(book, code)
    steep_out = weights["steep_out"][1]
    malt = weights["off_kiln"][0] if "off_kiln" in weights else weights["steep_out"][0]
    assert steep_out is not None
    return WaterUse(
        piece=code,
        charge_tonnes=piece.charge_tonnes,
        charge_moisture=piece.charge_moisture,
        steep_out_moisture=steep_out,
        metered_m3=as_number(row, "metered_m3"),
        malt_tonnes=malt,
    )


def record_water(
    book: Book, piece: str, metered_m3: float, on: dt.date, note: str = ""
) -> WaterUse:
    """Write down what the water meter read across one steep."""
    get_piece(book, piece)
    if "steep_out" not in weighings(book, piece):
        raise StateError(
            f"{piece} has not been cast, so a meter reading cannot be split into "
            f"what was kept and what went to drain"
        )
    book.execute(
        f"INSERT INTO steep_water ({_COLUMNS}) VALUES (?, ?, ?, ?)",
        (piece, metered_m3, date_text(on), note),
    )
    return get_water(book, piece)


def get_water(book: Book, piece: str) -> WaterUse:
    """One steep's water, or say which piece was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM steep_water WHERE piece = ?", (piece,))
    if row is None:
        raise NotFoundError(f"no water reading recorded against {piece!r}")
    return _use(book, row)


def find_water(book: Book, piece: str) -> WaterUse | None:
    """One steep's water, or nothing."""
    return optional(lambda: get_water(book, piece))


def list_water(
    book: Book, since: dt.date | None = None, until: dt.date | None = None
) -> tuple[WaterUse, ...]:
    """Every reading, oldest first, over a stretch of days."""
    narrow = narrowing().since("on_day", since).until("on_day", until)
    rows = book.query(
        f"SELECT {_COLUMNS} FROM steep_water{narrow.where} ORDER BY on_day, piece", narrow.values
    )
    return tuple(_use(book, row) for row in rows)


def metered(book: Book, since: dt.date | None = None, until: dt.date | None = None) -> float:
    """Cubic metres metered over a stretch of days."""
    narrow = narrowing().since("on_day", since).until("on_day", until)
    total = book.scalar(f"SELECT total(metered_m3) FROM steep_water{narrow.where}", narrow.values)
    return float(total or 0.0)


def to_drain(book: Book, since: dt.date | None = None, until: dt.date | None = None) -> float:
    """Cubic metres that went out dirty, which is the effluent bill."""
    return sum(use.to_drain_m3 for use in list_water(book, since, until))


def unmetered(book: Book) -> tuple[str, ...]:
    """Every cast piece with no water reading against it, oldest first."""
    rows = book.query(
        "SELECT p.code FROM piece p "
        "JOIN weighing w ON w.piece = p.code AND w.point = 'steep_out' "
        "LEFT JOIN steep_water s ON s.piece = p.code "
        "WHERE s.piece IS NULL ORDER BY p.started, p.code"
    )
    return tuple(as_text(row, "code") for row in rows)


def heavy(book: Book, since: dt.date | None = None) -> tuple[WaterUse, ...]:
    """Every piece over the band, which is a bill rather than a fault."""
    return tuple(use for use in list_water(book, since) if use.heavy)
