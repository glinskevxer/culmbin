"""Reading and writing the party register."""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Role
from culmbin.model.party import Party, Register, register_of
from culmbin.store.book import Book
from culmbin.store.query import optional
from culmbin.store.rows import (
    as_date,
    as_enum,
    as_optional_date,
    as_optional_text,
    as_text,
    date_text,
    optional_date_text,
)

_COLUMNS = "code, name, role, opened, closed, holding, note"


def _party(row: sqlite3.Row) -> Party:
    """Turn a row into a party."""
    return Party(
        code=as_text(row, "code"),
        name=as_text(row, "name"),
        role=as_enum(row, "role", Role),
        opened=as_date(row, "opened"),
        closed=as_optional_date(row, "closed"),
        holding=as_optional_text(row, "holding"),
        note=as_text(row, "note"),
    )


def add_party(book: Book, party: Party) -> Party:
    """Write a new party, and refuse to overwrite one that is there."""
    book.execute(
        f"INSERT INTO party ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            party.code,
            party.name,
            party.role,
            date_text(party.opened),
            optional_date_text(party.closed),
            party.holding,
            party.note,
        ),
    )
    return party


def update_party(book: Book, party: Party) -> Party:
    """Write a party that is already there, and refuse one that is not."""
    cursor = book.execute(
        "UPDATE party SET name = ?, role = ?, opened = ?, closed = ?, holding = ?, note = ? "
        "WHERE code = ?",
        (
            party.name,
            party.role,
            date_text(party.opened),
            optional_date_text(party.closed),
            party.holding,
            party.note,
            party.code,
        ),
    )
    if cursor.rowcount == 0:
        raise NotFoundError(f"no party called {party.code!r}")
    return party


def get_party(book: Book, code: str) -> Party:
    """One party, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM party WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no party called {code!r}")
    return _party(row)


def find_party(book: Book, code: str) -> Party | None:
    """One party, or nothing, for callers that treat absence as an answer."""
    return optional(lambda: get_party(book, code))


def list_parties(book: Book, role: Role | None = None) -> Register:
    """Every party, or everybody in one role, in code order."""
    if role is None:
        rows = book.query(f"SELECT {_COLUMNS} FROM party ORDER BY code")
    else:
        rows = book.query(f"SELECT {_COLUMNS} FROM party WHERE role = ? ORDER BY code", (role,))
    return register_of([_party(row) for row in rows])


def close_party(book: Book, code: str, on: dt.date) -> Party:
    """Stop trading with somebody from a day.

    Closing somebody who is already closed is refused rather than moved,
    because the second date is nearly always a typing mistake and the first
    one is on a contract somewhere.
    """
    party = get_party(book, code)
    if party.closed is not None:
        raise ConflictError(f"{party.code} was already closed on {party.closed}")
    closed = Party(
        code=party.code,
        name=party.name,
        role=party.role,
        opened=party.opened,
        closed=on,
        holding=party.holding,
        note=party.note,
    )
    return update_party(book, closed)
