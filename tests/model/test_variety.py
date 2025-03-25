"""The variety list.

The approval is a fact here and a judgement somewhere else, and these tests
are about keeping it that way.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import NotFoundError, ValidationError
from culmbin.model.enums import Approval, Habit
from culmbin.model.variety import ON_THE_LIST, Variety, variety_list_of

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


def test_a_variety_prints_as_name_and_habit() -> None:
    assert str(variety()) == "Laureate (spring)"


def test_a_variety_needs_a_code_and_a_name() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        variety("  ")
    with pytest.raises(ValidationError, match="has no name"):
        variety(name=" ")


def test_approved_and_provisional_are_on_the_list() -> None:
    assert variety().on_the_list
    assert variety(approval=Approval.PROVISIONAL).on_the_list


def test_under_test_is_not_on_the_list() -> None:
    """It is being looked at, which is not the same as being on it."""
    assert not variety(approval=Approval.UNDER_TEST).on_the_list


def test_the_two_that_count_are_the_two_in_the_constant() -> None:
    assert frozenset({Approval.APPROVED, Approval.PROVISIONAL}) == ON_THE_LIST


def test_a_withdrawal_needs_a_date() -> None:
    with pytest.raises(ValidationError, match="no date says when"):
        variety(approval=Approval.WITHDRAWN)


def test_a_withdrawal_date_without_a_withdrawal_is_refused() -> None:
    with pytest.raises(ValidationError, match="not withdrawn"):
        variety(withdrawn=dt.date(2024, 6, 1))


def test_a_withdrawal_before_the_listing_is_refused() -> None:
    with pytest.raises(ValidationError, match="withdrawn before"):
        variety(approval=Approval.WITHDRAWN, withdrawn=dt.date(2017, 1, 1))


def test_nothing_was_on_the_list_before_it_was_listed() -> None:
    assert not variety().on_the_list_on(dt.date(2018, 11, 30))
    assert variety().on_the_list_on(LISTED)


def test_a_withdrawn_variety_was_on_the_list_until_it_went() -> None:
    """This is the whole reason the question takes a date."""
    gone = variety(approval=Approval.WITHDRAWN, withdrawn=dt.date(2024, 6, 1))
    assert gone.on_the_list_on(dt.date(2024, 5, 31))
    assert not gone.on_the_list_on(dt.date(2024, 6, 1))
    assert not gone.on_the_list


def test_under_test_was_never_on_the_list_on_any_day() -> None:
    testing = variety(approval=Approval.UNDER_TEST)
    assert not testing.on_the_list_on(LISTED)
    assert not testing.on_the_list_on(dt.date(2025, 1, 1))


def test_a_list_looks_a_variety_up() -> None:
    listing = variety_list_of([variety("LAUR"), variety("DIAB", name="Diablo")])
    assert listing["DIAB"].name == "Diablo"
    assert len(listing) == 2


def test_a_variety_that_is_not_there_says_what_was_asked_for() -> None:
    with pytest.raises(NotFoundError, match="TIPP"):
        variety_list_of([variety()])["TIPP"]


def test_two_varieties_with_one_code_are_refused() -> None:
    with pytest.raises(ValidationError, match="share the code LAUR"):
        variety_list_of([variety("LAUR"), variety("LAUR", name="Laureate again")])


def test_a_list_reports_who_was_on_it_on_a_day() -> None:
    listing = variety_list_of(
        [
            variety("LAUR"),
            variety(
                "PROP",
                name="Propino",
                approval=Approval.WITHDRAWN,
                withdrawn=dt.date(2023, 6, 1),
            ),
            variety("NEWY", name="New One", approval=Approval.UNDER_TEST),
        ]
    )
    codes = [item.code for item in listing.on_the_list_on(dt.date(2024, 1, 1))]
    assert codes == ["LAUR"]
    codes = [item.code for item in listing.on_the_list_on(dt.date(2022, 1, 1))]
    assert codes == ["LAUR", "PROP"]


def test_a_list_splits_by_habit() -> None:
    listing = variety_list_of([variety("LAUR"), variety("CRAF", name="Craft", habit=Habit.WINTER)])
    assert [item.code for item in listing.of_habit(Habit.WINTER)] == ["CRAF"]
    assert [item.code for item in listing.of_habit(Habit.SPRING)] == ["LAUR"]


def test_a_list_iterates_in_order() -> None:
    listing = variety_list_of([variety("LAUR"), variety("DIAB", name="Diablo")])
    assert [item.code for item in listing] == ["LAUR", "DIAB"]
