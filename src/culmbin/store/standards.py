"""Reading and writing the intake quality standards.

A standard is written down and then left alone. Purchases name it, deliveries
are graded against it, and settlements quote it, so changing a threshold on
a standard that has been used restates money that has already been paid.

There is therefore no update here. A season with different thresholds is a
new standard with a new name, and the old one stays in the book for as long
as anything refers to it, which is forever.
"""

from __future__ import annotations

import sqlite3

from culmbin.errors import ConflictError, NotFoundError
from culmbin.intake.standard import Standard
from culmbin.store.book import Book
from culmbin.store.rows import as_money, as_number, as_text, money_text

_COLUMNS = (
    "name, moisture_base, moisture_reject, nitrogen_min, nitrogen_max, nitrogen_reject, "
    "screenings_free, screenings_reject, germination_floor, energy_floor, admixture_reject, "
    "drying_per_point, nitrogen_step, nitrogen_per_step"
)


def _standard(row: sqlite3.Row) -> Standard:
    """Turn a row into a standard."""
    return Standard(
        name=as_text(row, "name"),
        moisture_base=as_number(row, "moisture_base"),
        moisture_reject=as_number(row, "moisture_reject"),
        nitrogen_min=as_number(row, "nitrogen_min"),
        nitrogen_max=as_number(row, "nitrogen_max"),
        nitrogen_reject=as_number(row, "nitrogen_reject"),
        screenings_free=as_number(row, "screenings_free"),
        screenings_reject=as_number(row, "screenings_reject"),
        germination_floor=as_number(row, "germination_floor"),
        energy_floor=as_number(row, "energy_floor"),
        admixture_reject=as_number(row, "admixture_reject"),
        drying_per_point=as_money(row, "drying_per_point"),
        nitrogen_step=as_number(row, "nitrogen_step"),
        nitrogen_per_step=as_money(row, "nitrogen_per_step"),
    )


def add_standard(book: Book, standard: Standard) -> Standard:
    """Write a new standard, and refuse to write over one that is there."""
    book.execute(
        f"INSERT INTO standard ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            standard.name,
            standard.moisture_base,
            standard.moisture_reject,
            standard.nitrogen_min,
            standard.nitrogen_max,
            standard.nitrogen_reject,
            standard.screenings_free,
            standard.screenings_reject,
            standard.germination_floor,
            standard.energy_floor,
            standard.admixture_reject,
            money_text(standard.drying_per_point),
            standard.nitrogen_step,
            money_text(standard.nitrogen_per_step),
        ),
    )
    return standard


def get_standard(book: Book, name: str) -> Standard:
    """One standard, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM standard WHERE name = ?", (name,))
    if row is None:
        raise NotFoundError(f"no standard called {name!r}")
    return _standard(row)


def find_standard(book: Book, name: str) -> Standard | None:
    """One standard, or nothing."""
    try:
        return get_standard(book, name)
    except NotFoundError:
        return None


def list_standards(book: Book) -> tuple[Standard, ...]:
    """Every standard, in name order."""
    rows = book.query(f"SELECT {_COLUMNS} FROM standard ORDER BY name")
    return tuple(_standard(row) for row in rows)


def copy_standard(book: Book, name: str, into: str) -> Standard:
    """Write a new standard with the thresholds of an old one.

    This is how next season starts: copy last season's, then the thresholds
    that moved are edited on the copy before it is written. Copying onto a
    name that is taken is refused, because that would be an edit.
    """
    if find_standard(book, into) is not None:
        raise ConflictError(f"there is already a standard called {into!r}")
    old = get_standard(book, name)
    return add_standard(
        book,
        Standard(
            name=into,
            moisture_base=old.moisture_base,
            moisture_reject=old.moisture_reject,
            nitrogen_min=old.nitrogen_min,
            nitrogen_max=old.nitrogen_max,
            nitrogen_reject=old.nitrogen_reject,
            screenings_free=old.screenings_free,
            screenings_reject=old.screenings_reject,
            germination_floor=old.germination_floor,
            energy_floor=old.energy_floor,
            admixture_reject=old.admixture_reject,
            drying_per_point=old.drying_per_point,
            nitrogen_step=old.nitrogen_step,
            nitrogen_per_step=old.nitrogen_per_step,
        ),
    )
