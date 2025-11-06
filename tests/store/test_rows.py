"""Turning a SQLite row into a value and back.

This is the one boundary where a date becomes text, so the tests are about
what happens when the text is not a date.

The nullable column is called `absent` rather than `nothing`, because
`NOTHING` is a SQLite keyword and an unquoted one is a syntax error.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Iterator
from decimal import Decimal

import pytest

from culmbin.errors import ValidationError
from culmbin.model.enums import Role
from culmbin.store.book import MEMORY, Book
from culmbin.store.rows import (
    as_count,
    as_date,
    as_enum,
    as_money,
    as_number,
    as_optional_date,
    as_optional_number,
    as_optional_text,
    as_text,
    date_text,
    money_text,
    optional_date_text,
    row_values,
)


@pytest.fixture
def row() -> Iterator[sqlite3.Row]:
    with Book.open(MEMORY) as book:
        book.executescript(
            "CREATE TABLE thing ("
            "  day TEXT, absent TEXT, name TEXT, weight REAL, count INTEGER,"
            "  role TEXT, price TEXT, wrong REAL, flag INTEGER"
            ");"
        )
        book.execute(
            "INSERT INTO thing VALUES ('2025-11-04', NULL, 'malt', 28.18, 3, "
            "'grower', '232.50', 'not a date', 1)"
        )
        yield book.one("SELECT * FROM thing")


def test_a_date_goes_out_as_text() -> None:
    assert date_text(dt.date(2025, 11, 4)) == "2025-11-04"
    assert optional_date_text(None) is None
    assert optional_date_text(dt.date(2025, 11, 4)) == "2025-11-04"


def test_a_date_comes_back(row: sqlite3.Row) -> None:
    assert as_date(row, "day") == dt.date(2025, 11, 4)
    assert as_optional_date(row, "absent") is None
    assert as_optional_date(row, "day") == dt.date(2025, 11, 4)


def test_something_that_is_not_a_date_says_which_column(row: sqlite3.Row) -> None:
    with pytest.raises(ValidationError, match="wrong holds"):
        as_date(row, "wrong")
    with pytest.raises(ValidationError, match="name holds"):
        as_date(row, "name")


def test_a_string_comes_back_out_of_a_row(row: sqlite3.Row) -> None:
    assert as_text(row, "name") == "malt"
    assert as_optional_text(row, "absent") is None


def test_something_that_is_not_text_says_which_column(row: sqlite3.Row) -> None:
    with pytest.raises(ValidationError, match="weight holds"):
        as_text(row, "weight")


def test_a_number_comes_back(row: sqlite3.Row) -> None:
    assert as_number(row, "weight") == pytest.approx(28.18)
    assert as_number(row, "count") == pytest.approx(3.0)
    assert as_optional_number(row, "absent") is None


def test_something_that_is_not_a_number_says_which_column(row: sqlite3.Row) -> None:
    with pytest.raises(ValidationError, match="name holds"):
        as_number(row, "name")


def test_a_whole_number_comes_back(row: sqlite3.Row) -> None:
    assert as_count(row, "count") == 3


def test_a_real_is_not_a_whole_number(row: sqlite3.Row) -> None:
    with pytest.raises(ValidationError, match="whole number"):
        as_count(row, "weight")


def test_an_enum_comes_back(row: sqlite3.Row) -> None:
    assert as_enum(row, "role", Role) is Role.GROWER


def test_something_that_is_not_a_member_says_so(row: sqlite3.Row) -> None:
    """A value that fails here came from a book something else wrote."""
    with pytest.raises(ValidationError, match="not a Role"):
        as_enum(row, "name", Role)


def test_money_goes_out_as_text_and_comes_back_as_a_decimal(row: sqlite3.Row) -> None:
    """232.50 is not a float, and a settlement a hundredth of a penny out is one to explain."""
    assert money_text(Decimal("232.5")) == "232.50"
    assert as_money(row, "price") == Decimal("232.50")


def test_something_that_is_not_a_price_says_which_column(row: sqlite3.Row) -> None:
    with pytest.raises(ValidationError, match="weight holds"):
        as_money(row, "weight")
    with pytest.raises(ValidationError, match="name holds"):
        as_money(row, "name")


def test_a_row_comes_back_as_a_dictionary(row: sqlite3.Row) -> None:
    values = row_values(row)
    assert values["name"] == "malt"
    assert values["absent"] is None
    assert len(values) == 9
