"""Turning a SQLite row into a value and back.

SQLite has five storage classes and none of them is a date. Everything in
this book stores a date as an ISO string, which sorts correctly, reads
correctly in a `sqlite3` shell and compares correctly in SQL, and which has
to be converted at exactly one boundary or it will be converted at fifty.

This is that boundary.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Any, TypeVar

from culmbin.errors import ValidationError

E = TypeVar("E", bound=str)


def date_text(day: dt.date) -> str:
    """A date as it is stored."""
    return day.isoformat()


def optional_date_text(day: dt.date | None) -> str | None:
    """A date or nothing, as it is stored."""
    return None if day is None else day.isoformat()


def as_date(row: sqlite3.Row, column: str) -> dt.date:
    """A date out of a row, saying which column it was when it is not one."""
    value = row[column]
    if not isinstance(value, str):
        raise ValidationError(f"{column} holds {value!r}, which is not a date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{column} holds {value!r}, which is not a date") from exc


def as_optional_date(row: sqlite3.Row, column: str) -> dt.date | None:
    """A date or nothing out of a row."""
    return None if row[column] is None else as_date(row, column)


def as_text(row: sqlite3.Row, column: str) -> str:
    """A string out of a row."""
    value = row[column]
    if not isinstance(value, str):
        raise ValidationError(f"{column} holds {value!r}, which is not text")
    return value


def as_optional_text(row: sqlite3.Row, column: str) -> str | None:
    """A string or nothing out of a row."""
    return None if row[column] is None else as_text(row, column)


def as_number(row: sqlite3.Row, column: str) -> float:
    """A number out of a row."""
    value = row[column]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(f"{column} holds {value!r}, which is not a number")
    return float(value)


def as_optional_number(row: sqlite3.Row, column: str) -> float | None:
    """A number or nothing out of a row."""
    return None if row[column] is None else as_number(row, column)


def as_count(row: sqlite3.Row, column: str) -> int:
    """A whole number out of a row."""
    value = row[column]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{column} holds {value!r}, which is not a whole number")
    return int(value)


def as_enum(row: sqlite3.Row, column: str, kind: type[E]) -> E:
    """A member of a closed vocabulary out of a row.

    The book has a CHECK constraint for every one of these, so a value that
    fails here came from a book written by something other than this
    package, which is worth saying plainly rather than crashing on.
    """
    value = as_text(row, column)
    try:
        return kind(value)
    except ValueError as exc:
        raise ValidationError(f"{column} holds {value!r}, which is not a {kind.__name__}") from exc


def row_values(row: sqlite3.Row) -> dict[str, Any]:
    """A row as a plain dictionary, for reporting and for tests."""
    return dict(zip(row.keys(), tuple(row), strict=True))
