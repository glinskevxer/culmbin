"""The variety list in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Approval, Habit
from culmbin.model.variety import Variety
from culmbin.store.book import Book
from culmbin.store.varieties import (
    add_variety,
    find_variety,
    get_variety,
    list_varieties,
    promote_variety,
    update_variety,
    withdraw_variety,
)

LISTED = dt.date(2018, 12, 1)


def variety(code: str = "LAUR", **kwargs: object) -> Variety:
    fields: dict[str, object] = {
        "name": "Laureate",
        "habit": Habit.SPRING,
        "approval": Approval.APPROVED,
        "listed": LISTED,
    }
    fields.update(kwargs)
    return Variety(code=code, **fields)  # type: ignore[arg-type]


def test_a_variety_reads_back_the_way_it_went_in(book: Book) -> None:
    add_variety(book, variety())
    assert get_variety(book, "LAUR") == variety()


def test_a_withdrawn_variety_keeps_its_date(book: Book) -> None:
    add_variety(book, variety(approval=Approval.WITHDRAWN, withdrawn=dt.date(2024, 6, 1)))
    assert get_variety(book, "LAUR").withdrawn == dt.date(2024, 6, 1)


def test_a_variety_that_is_not_there_says_which_one(book: Book) -> None:
    with pytest.raises(NotFoundError, match="LAUR"):
        get_variety(book, "LAUR")


def test_finding_treats_absence_as_an_answer(book: Book) -> None:
    assert find_variety(book, "LAUR") is None


def test_adding_the_same_code_twice_is_refused(book: Book) -> None:
    add_variety(book, variety())
    with pytest.raises(ConflictError):
        add_variety(book, variety(name="Laureate again"))


def test_updating_something_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError):
        update_variety(book, variety())


def test_the_list_comes_back_in_code_order(book: Book) -> None:
    add_variety(book, variety("LAUR"))
    add_variety(book, variety("DIAB", name="Diablo"))
    assert [item.code for item in list_varieties(book)] == ["DIAB", "LAUR"]


def test_the_list_filters_by_habit(book: Book) -> None:
    add_variety(book, variety("LAUR"))
    add_variety(book, variety("CRAF", name="Craft", habit=Habit.WINTER))
    assert [item.code for item in list_varieties(book, Habit.WINTER)] == ["CRAF"]


def test_promoting_moves_it_along(book: Book) -> None:
    add_variety(book, variety(approval=Approval.UNDER_TEST))
    promote_variety(book, "LAUR", Approval.PROVISIONAL)
    assert get_variety(book, "LAUR").approval is Approval.PROVISIONAL


def test_promoting_to_withdrawn_is_refused(book: Book) -> None:
    """Withdrawal needs a date, so it is not something a promotion can do."""
    add_variety(book, variety())
    with pytest.raises(ConflictError, match="needs a date"):
        promote_variety(book, "LAUR", Approval.WITHDRAWN)


def test_a_withdrawn_variety_does_not_come_back(book: Book) -> None:
    add_variety(book, variety())
    withdraw_variety(book, "LAUR", dt.date(2024, 6, 1))
    with pytest.raises(ConflictError, match="does not come back"):
        promote_variety(book, "LAUR", Approval.APPROVED)


def test_withdrawing_sets_the_date_and_the_approval(book: Book) -> None:
    add_variety(book, variety())
    withdraw_variety(book, "LAUR", dt.date(2024, 6, 1))
    read = get_variety(book, "LAUR")
    assert read.approval is Approval.WITHDRAWN
    assert read.withdrawn == dt.date(2024, 6, 1)
    assert not read.on_the_list


def test_withdrawing_twice_is_refused(book: Book) -> None:
    add_variety(book, variety())
    withdraw_variety(book, "LAUR", dt.date(2024, 6, 1))
    with pytest.raises(ConflictError, match="already withdrawn"):
        withdraw_variety(book, "LAUR", dt.date(2024, 7, 1))


def test_withdrawing_something_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError):
        withdraw_variety(book, "LAUR", dt.date(2024, 6, 1))
