"""Reading and writing the variety list."""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Approval, Habit
from culmbin.model.variety import Variety, VarietyList, variety_list_of
from culmbin.store.book import Book
from culmbin.store.query import optional
from culmbin.store.rows import (
    as_date,
    as_enum,
    as_optional_date,
    as_text,
    date_text,
    optional_date_text,
)

_COLUMNS = "code, name, habit, approval, listed, withdrawn"


def _variety(row: sqlite3.Row) -> Variety:
    """Turn a row into a variety."""
    return Variety(
        code=as_text(row, "code"),
        name=as_text(row, "name"),
        habit=as_enum(row, "habit", Habit),
        approval=as_enum(row, "approval", Approval),
        listed=as_date(row, "listed"),
        withdrawn=as_optional_date(row, "withdrawn"),
    )


def add_variety(book: Book, variety: Variety) -> Variety:
    """Write a new variety."""
    book.execute(
        f"INSERT INTO variety ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
        (
            variety.code,
            variety.name,
            variety.habit,
            variety.approval,
            date_text(variety.listed),
            optional_date_text(variety.withdrawn),
        ),
    )
    return variety


def update_variety(book: Book, variety: Variety) -> Variety:
    """Write a variety that is already there."""
    cursor = book.execute(
        "UPDATE variety SET name = ?, habit = ?, approval = ?, listed = ?, withdrawn = ? "
        "WHERE code = ?",
        (
            variety.name,
            variety.habit,
            variety.approval,
            date_text(variety.listed),
            optional_date_text(variety.withdrawn),
            variety.code,
        ),
    )
    if cursor.rowcount == 0:
        raise NotFoundError(f"no variety called {variety.code!r}")
    return variety


def get_variety(book: Book, code: str) -> Variety:
    """One variety, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM variety WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no variety called {code!r}")
    return _variety(row)


def find_variety(book: Book, code: str) -> Variety | None:
    """One variety, or nothing."""
    return optional(lambda: get_variety(book, code))


def list_varieties(book: Book, habit: Habit | None = None) -> VarietyList:
    """Every variety, or every one of a habit, in code order."""
    if habit is None:
        rows = book.query(f"SELECT {_COLUMNS} FROM variety ORDER BY code")
    else:
        rows = book.query(f"SELECT {_COLUMNS} FROM variety WHERE habit = ? ORDER BY code", (habit,))
    return variety_list_of([_variety(row) for row in rows])


def promote_variety(book: Book, code: str, approval: Approval) -> Variety:
    """Move a variety along the list.

    Withdrawal is a different operation because it needs a date, so this
    refuses it rather than writing a withdrawal with no date and letting the
    record raise somewhere further along.
    """
    if approval is Approval.WITHDRAWN:
        raise ConflictError("withdrawing needs a date, so it is not a promotion")
    variety = get_variety(book, code)
    if variety.approval is Approval.WITHDRAWN:
        raise ConflictError(f"{code} was withdrawn on {variety.withdrawn} and does not come back")
    return update_variety(
        book,
        Variety(
            code=variety.code,
            name=variety.name,
            habit=variety.habit,
            approval=approval,
            listed=variety.listed,
            withdrawn=None,
        ),
    )


def withdraw_variety(book: Book, code: str, on: dt.date) -> Variety:
    """Take a variety off the list from a day."""
    variety = get_variety(book, code)
    if variety.approval is Approval.WITHDRAWN:
        raise ConflictError(f"{code} was already withdrawn on {variety.withdrawn}")
    return update_variety(
        book,
        Variety(
            code=variety.code,
            name=variety.name,
            habit=variety.habit,
            approval=Approval.WITHDRAWN,
            listed=variety.listed,
            withdrawn=on,
        ),
    )
