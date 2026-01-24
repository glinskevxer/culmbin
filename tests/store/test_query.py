"""Building a narrowed query, and asking for something that may not be there."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.store.query import Narrowing, narrowing, optional


def test_an_empty_narrowing_has_no_clause() -> None:
    narrow = narrowing()
    assert narrow.where == ""
    assert narrow.values == []
    assert len(narrow) == 0


def test_one_clause_carries_its_leading_space() -> None:
    narrow = narrowing().always("code = ?", "HOLB")
    assert narrow.where == " WHERE code = ?"
    assert narrow.values == ["HOLB"]


def test_two_clauses_are_joined_with_and() -> None:
    narrow = narrowing().always("code = ?", "HOLB").always("role = ?", "grower")
    assert narrow.where == " WHERE code = ? AND role = ?"
    assert narrow.values == ["HOLB", "grower"]


def test_a_filter_of_nothing_adds_nothing() -> None:
    """Which is why the caller never writes an `if`."""
    narrow = narrowing().maybe("code = ?", None).maybe("role = ?", "grower")
    assert narrow.where == " WHERE role = ?"
    assert narrow.values == ["grower"]


def test_a_clause_and_its_value_cannot_get_out_of_step() -> None:
    narrow = narrowing().maybe("a = ?", 1).maybe("b = ?", None).maybe("c = ?", 3)
    assert len(narrow) == len(narrow.values)


def test_a_day_filter_turns_into_stored_text() -> None:
    narrow = narrowing().since("arrived", dt.date(2025, 9, 18))
    assert narrow.where == " WHERE arrived >= ?"
    assert narrow.values == ["2025-09-18"]


def test_a_day_filter_of_nothing_adds_nothing() -> None:
    narrow = narrowing().since("arrived", None).until("arrived", None)
    assert narrow.where == ""


def test_both_ends_of_a_window_can_be_given() -> None:
    narrow = (
        narrowing().since("arrived", dt.date(2025, 9, 1)).until("arrived", dt.date(2025, 9, 30))
    )
    assert narrow.where == " WHERE arrived >= ? AND arrived <= ?"
    assert narrow.values == ["2025-09-01", "2025-09-30"]


def test_a_set_of_values_goes_through_as_parameters() -> None:
    """An `IN` list is the one clause that tempts everybody into building SQL."""
    narrow = narrowing().one_of("state", ["open", "investigating"])
    assert narrow.where == " WHERE state IN (?, ?)"
    assert narrow.values == ["open", "investigating"]


def test_a_set_of_nothing_matches_nothing() -> None:
    narrow = narrowing().one_of("state", [])
    assert narrow.where == " WHERE 1 = 0"
    assert narrow.values == []


def test_a_clause_with_no_value_is_still_a_clause() -> None:
    narrow = narrowing().always("sample IS NULL")
    assert narrow.where == " WHERE sample IS NULL"
    assert narrow.values == []


def test_a_narrowing_can_be_built_directly() -> None:
    assert Narrowing().where == ""


def test_a_getter_that_finds_something_gives_it_back() -> None:
    assert optional(lambda: "found") == "found"


def test_a_getter_that_finds_nothing_gives_nothing_back() -> None:
    def missing() -> str:
        raise NotFoundError("no party called 'HOLB'")

    assert optional(missing) is None


def test_another_kind_of_failure_is_not_swallowed() -> None:
    """Only a not-found becomes nothing. Everything else is still a problem."""

    def broken() -> str:
        raise ConflictError("the book already holds this one")

    with pytest.raises(ConflictError):
        optional(broken)
