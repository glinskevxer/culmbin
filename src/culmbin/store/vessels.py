"""Reading and writing the vessel register."""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import VesselKind
from culmbin.model.plant import Plant, Vessel, plant_of
from culmbin.store.book import Book
from culmbin.store.query import optional
from culmbin.store.rows import (
    as_date,
    as_enum,
    as_optional_date,
    as_optional_number,
    as_text,
    date_text,
    optional_date_text,
)

_COLUMNS = "code, name, kind, commissioned, charge_limit_t, floor_area_m2, depth_limit_cm, retired"


def _vessel(row: sqlite3.Row) -> Vessel:
    """Turn a row into a vessel."""
    return Vessel(
        code=as_text(row, "code"),
        name=as_text(row, "name"),
        kind=as_enum(row, "kind", VesselKind),
        commissioned=as_date(row, "commissioned"),
        charge_limit_t=as_optional_number(row, "charge_limit_t"),
        floor_area_m2=as_optional_number(row, "floor_area_m2"),
        depth_limit_cm=as_optional_number(row, "depth_limit_cm"),
        retired=as_optional_date(row, "retired"),
    )


def add_vessel(book: Book, vessel: Vessel) -> Vessel:
    """Write a new vessel."""
    book.execute(
        f"INSERT INTO vessel ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            vessel.code,
            vessel.name,
            vessel.kind,
            date_text(vessel.commissioned),
            vessel.charge_limit_t,
            vessel.floor_area_m2,
            vessel.depth_limit_cm,
            optional_date_text(vessel.retired),
        ),
    )
    return vessel


def update_vessel(book: Book, vessel: Vessel) -> Vessel:
    """Write a vessel that is already there."""
    cursor = book.execute(
        "UPDATE vessel SET name = ?, kind = ?, commissioned = ?, charge_limit_t = ?, "
        "floor_area_m2 = ?, depth_limit_cm = ?, retired = ? WHERE code = ?",
        (
            vessel.name,
            vessel.kind,
            date_text(vessel.commissioned),
            vessel.charge_limit_t,
            vessel.floor_area_m2,
            vessel.depth_limit_cm,
            optional_date_text(vessel.retired),
            vessel.code,
        ),
    )
    if cursor.rowcount == 0:
        raise NotFoundError(f"no vessel called {vessel.code!r}")
    return vessel


def get_vessel(book: Book, code: str) -> Vessel:
    """One vessel, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM vessel WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no vessel called {code!r}")
    return _vessel(row)


def find_vessel(book: Book, code: str) -> Vessel | None:
    """One vessel, or nothing."""
    return optional(lambda: get_vessel(book, code))


def list_vessels(book: Book, kind: VesselKind | None = None) -> Plant:
    """Every vessel, or every one of a kind, in code order."""
    if kind is None:
        rows = book.query(f"SELECT {_COLUMNS} FROM vessel ORDER BY code")
    else:
        rows = book.query(f"SELECT {_COLUMNS} FROM vessel WHERE kind = ? ORDER BY code", (kind,))
    return plant_of([_vessel(row) for row in rows])


def retire_vessel(book: Book, code: str, on: dt.date) -> Vessel:
    """Take a vessel out of service from a day."""
    vessel = get_vessel(book, code)
    if vessel.retired is not None:
        raise ConflictError(f"{code} was already retired on {vessel.retired}")
    return update_vessel(
        book,
        Vessel(
            code=vessel.code,
            name=vessel.name,
            kind=vessel.kind,
            commissioned=vessel.commissioned,
            charge_limit_t=vessel.charge_limit_t,
            floor_area_m2=vessel.floor_area_m2,
            depth_limit_cm=vessel.depth_limit_cm,
            retired=on,
        ),
    )
