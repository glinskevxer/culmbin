"""Reading and writing purchases, and how much of one is left to come.

The interesting function here is `outstanding`. A purchase is drawn down by
the deliveries against it, and the tonnage that counts is the *settled*
tonnage, not what came off the lorry. A grower who delivers four hundred and
eighty wet tonnes against a four hundred and eighty tonne contract has not
finished it, and telling him he has is the sort of mistake that is found in
January.

Rejected loads count for nothing, which is the same rule again from the
other side.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.intake import Purchase
from culmbin.store.book import Book
from culmbin.store.query import narrowing, optional
from culmbin.store.rows import (
    as_count,
    as_date,
    as_money,
    as_number,
    as_text,
    date_text,
    money_text,
)
from culmbin.units.season import Window

_COLUMNS = (
    "code, party, variety, crop_year, tonnes, window_start, window_end, "
    "standard, price_per_tonne, signed"
)


def _purchase(row: sqlite3.Row) -> Purchase:
    """Turn a row into a purchase."""
    return Purchase(
        code=as_text(row, "code"),
        party=as_text(row, "party"),
        variety=as_text(row, "variety"),
        crop_year=as_count(row, "crop_year"),
        tonnes=as_number(row, "tonnes"),
        window=Window(as_date(row, "window_start"), as_date(row, "window_end")),
        standard=as_text(row, "standard"),
        price_per_tonne=as_money(row, "price_per_tonne"),
        signed=as_date(row, "signed"),
    )


def add_purchase(book: Book, purchase: Purchase) -> Purchase:
    """Write a new purchase."""
    book.execute(
        f"INSERT INTO purchase ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            purchase.code,
            purchase.party,
            purchase.variety,
            purchase.crop_year,
            purchase.tonnes,
            date_text(purchase.window.start),
            date_text(purchase.window.end),
            purchase.standard,
            money_text(purchase.price_per_tonne),
            date_text(purchase.signed),
        ),
    )
    return purchase


def get_purchase(book: Book, code: str) -> Purchase:
    """One purchase, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM purchase WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no purchase called {code!r}")
    return _purchase(row)


def find_purchase(book: Book, code: str) -> Purchase | None:
    """One purchase, or nothing."""
    return optional(lambda: get_purchase(book, code))


def list_purchases(
    book: Book, party: str | None = None, crop_year: int | None = None
) -> tuple[Purchase, ...]:
    """Every purchase, in code order, narrowed by grower and by crop."""
    narrow = narrowing().maybe("party = ?", party).maybe("crop_year = ?", crop_year)
    rows = book.query(f"SELECT {_COLUMNS} FROM purchase{narrow.where} ORDER BY code", narrow.values)
    return tuple(_purchase(row) for row in rows)


def extend_window(book: Book, code: str, until: dt.date) -> Purchase:
    """Move a purchase's window out to a later day.

    Only outwards. A window that is pulled in would put deliveries already
    taken outside the contract they came in on, and the fix for that is a
    conversation rather than an update.
    """
    purchase = get_purchase(book, code)
    if until <= purchase.window.end:
        raise ConflictError(
            f"{code} already runs to {purchase.window.end}, so {until} is not an extension"
        )
    book.execute("UPDATE purchase SET window_end = ? WHERE code = ?", (date_text(until), code))
    return get_purchase(book, code)


def settled_against(book: Book, code: str) -> float:
    """The settled tonnage delivered against a purchase.

    Reads the grading rather than the weighbridge, because what draws a
    contract down is what we agreed arrived, not what the lorry weighed.
    """
    total = book.scalar(
        "SELECT total(g.settled_tonnes) FROM grading g "
        "JOIN delivery d ON d.ticket = g.ticket WHERE d.purchase = ?",
        (code,),
    )
    return float(total or 0.0)


def outstanding(book: Book, code: str) -> float:
    """How many tonnes of a purchase are still to come.

    Never below zero. A purchase can be over delivered, and what the office
    wants to know then is that there is nothing left, not that there is
    minus four tonnes left.
    """
    purchase = get_purchase(book, code)
    return max(0.0, purchase.tonnes - settled_against(book, code))


def is_complete(book: Book, code: str) -> bool:
    """Whether a purchase has been delivered in full."""
    return outstanding(book, code) <= 1e-9
