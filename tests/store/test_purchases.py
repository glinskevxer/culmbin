"""Purchases in the book, and how much of one is left to come."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.intake import Purchase
from culmbin.store.book import Book
from culmbin.store.purchases import (
    add_purchase,
    extend_window,
    find_purchase,
    get_purchase,
    is_complete,
    list_purchases,
    outstanding,
    settled_against,
)
from culmbin.units.season import Window

WINDOW = Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30))


def purchase(code: str = "P-2025-020", **kwargs: object) -> Purchase:
    fields: dict[str, object] = {
        "party": "WYKE",
        "variety": "DIAB",
        "crop_year": 2025,
        "tonnes": 300.0,
        "window": WINDOW,
        "standard": "malting 2025",
        "price_per_tonne": Decimal("228.00"),
        "signed": dt.date(2025, 3, 20),
    }
    fields.update(kwargs)
    return Purchase(code=code, **fields)  # type: ignore[arg-type]


def deliver(
    book: Book, ticket: str, settled: float, outcome: str = "accepted", net: float = 25.0
) -> None:
    """Write a delivery and a grading straight in, which is what draws a purchase down."""
    book.execute(
        "INSERT INTO delivery (ticket, purchase, party, arrived, gross_kg, tare_kg) "
        "VALUES (?, 'P-2025-014', 'HOLB', '2025-09-18', 40000.0, 15000.0)",
        (ticket,),
    )
    book.execute(
        "INSERT INTO grading (ticket, standard, outcome, net_tonnes, settled_tonnes, graded_on) "
        "VALUES (?, 'malting 2025', ?, ?, ?, '2025-09-18')",
        (ticket, outcome, max(net, settled), settled),
    )


def test_a_purchase_reads_back_the_way_it_went_in(stocked: Book) -> None:
    add_purchase(stocked, purchase())
    assert get_purchase(stocked, "P-2025-020") == purchase()


def test_the_price_comes_back_as_a_decimal(stocked: Book) -> None:
    add_purchase(stocked, purchase())
    assert get_purchase(stocked, "P-2025-020").price_per_tonne == Decimal("228.00")


def test_a_purchase_that_is_not_there_says_which_one(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="P-2025-099"):
        get_purchase(stocked, "P-2025-099")


def test_finding_treats_absence_as_an_answer(stocked: Book) -> None:
    assert find_purchase(stocked, "P-2025-099") is None


def test_a_purchase_against_a_grower_who_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_purchase(stocked, purchase(party="NOBODY"))


def test_a_purchase_on_a_variety_that_is_not_listed_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_purchase(stocked, purchase(variety="NOPE"))


def test_a_purchase_on_a_standard_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_purchase(stocked, purchase(standard="malting 2024"))


def test_the_listing_is_in_code_order(stocked: Book) -> None:
    add_purchase(stocked, purchase("P-2025-020"))
    assert [item.code for item in list_purchases(stocked)] == ["P-2025-014", "P-2025-020"]


def test_the_listing_narrows_by_grower_and_by_crop(stocked: Book) -> None:
    add_purchase(stocked, purchase("P-2025-020"))
    add_purchase(stocked, purchase("P-2024-003", crop_year=2024))
    assert [item.code for item in list_purchases(stocked, party="WYKE")] == [
        "P-2024-003",
        "P-2025-020",
    ]
    assert [item.code for item in list_purchases(stocked, crop_year=2024)] == ["P-2024-003"]


def test_a_window_can_be_pushed_out(stocked: Book) -> None:
    extend_window(stocked, "P-2025-014", dt.date(2025, 12, 20))
    assert get_purchase(stocked, "P-2025-014").window.end == dt.date(2025, 12, 20)


def test_a_window_cannot_be_pulled_in(stocked: Book) -> None:
    """Deliveries already taken would fall outside the contract they came in on."""
    with pytest.raises(ConflictError, match="not an extension"):
        extend_window(stocked, "P-2025-014", dt.date(2025, 10, 1))


def test_extending_something_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        extend_window(stocked, "P-2025-099", dt.date(2025, 12, 20))


def test_nothing_delivered_leaves_the_whole_purchase_outstanding(stocked: Book) -> None:
    assert settled_against(stocked, "P-2025-014") == pytest.approx(0.0)
    assert outstanding(stocked, "P-2025-014") == pytest.approx(480.0)
    assert not is_complete(stocked, "P-2025-014")


def test_a_delivery_draws_the_purchase_down_by_what_was_settled(stocked: Book) -> None:
    deliver(stocked, "W-1", settled=24.0)
    assert settled_against(stocked, "P-2025-014") == pytest.approx(24.0)
    assert outstanding(stocked, "P-2025-014") == pytest.approx(456.0)


def test_a_rejected_load_draws_nothing_down(stocked: Book) -> None:
    deliver(stocked, "W-1", settled=0.0, outcome="rejected")
    assert settled_against(stocked, "P-2025-014") == pytest.approx(0.0)
    assert outstanding(stocked, "P-2025-014") == pytest.approx(480.0)


def test_an_ungraded_delivery_draws_nothing_down(stocked: Book) -> None:
    """It is in the pit and it is not paid for, so it is not against the contract yet."""
    stocked.execute(
        "INSERT INTO delivery (ticket, purchase, party, arrived, gross_kg, tare_kg) "
        "VALUES ('W-9', 'P-2025-014', 'HOLB', '2025-09-18', 40000.0, 15000.0)"
    )
    assert settled_against(stocked, "P-2025-014") == pytest.approx(0.0)


def test_a_finished_purchase_says_so(stocked: Book) -> None:
    deliver(stocked, "W-1", settled=480.0, net=490.0)
    assert is_complete(stocked, "P-2025-014")
    assert outstanding(stocked, "P-2025-014") == pytest.approx(0.0)


def test_an_over_delivered_purchase_has_nothing_left_rather_than_less(stocked: Book) -> None:
    deliver(stocked, "W-1", settled=480.0, net=490.0)
    deliver(stocked, "W-2", settled=12.0)
    assert outstanding(stocked, "P-2025-014") == pytest.approx(0.0)
    assert settled_against(stocked, "P-2025-014") == pytest.approx(492.0)
