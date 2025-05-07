"""Deliveries in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Material
from culmbin.model.intake import Delivery
from culmbin.model.results import Result, analysis_of
from culmbin.store.analyses import save_analysis
from culmbin.store.book import Book
from culmbin.store.deliveries import (
    add_delivery,
    attach_sample,
    find_delivery,
    get_delivery,
    list_deliveries,
    unsampled,
)

ARRIVED = dt.date(2025, 9, 18)


def delivery(ticket: str = "W-24188", **kwargs: object) -> Delivery:
    fields: dict[str, object] = {
        "purchase": "P-2025-014",
        "party": "HOLB",
        "arrived": ARRIVED,
        "gross_kg": 43_820.0,
        "tare_kg": 15_640.0,
    }
    fields.update(kwargs)
    return Delivery(ticket=ticket, **fields)  # type: ignore[arg-type]


def sample(book: Book, reference: str = "B-2025-0918-03") -> str:
    save_analysis(
        book,
        analysis_of(reference, Material.BARLEY, ARRIVED, [Result("moisture", 12.4)]),
    )
    return reference


def test_a_delivery_reads_back_the_way_it_went_in(stocked: Book) -> None:
    add_delivery(stocked, delivery())
    assert get_delivery(stocked, "W-24188") == delivery()


def test_the_weights_survive_the_round_trip(stocked: Book) -> None:
    add_delivery(stocked, delivery())
    read = get_delivery(stocked, "W-24188")
    assert read.gross_kg == pytest.approx(43_820.0)
    assert read.net_tonnes == pytest.approx(28.18)


def test_a_haulier_and_a_vehicle_are_kept(stocked: Book) -> None:
    add_delivery(stocked, delivery(haulier="HAUL", vehicle="YJ19 KLM"))
    read = get_delivery(stocked, "W-24188")
    assert read.haulier == "HAUL"
    assert read.vehicle == "YJ19 KLM"


def test_a_delivery_that_is_not_there_says_which_ticket(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="W-99999"):
        get_delivery(stocked, "W-99999")


def test_finding_treats_absence_as_an_answer(stocked: Book) -> None:
    assert find_delivery(stocked, "W-99999") is None


def test_the_same_ticket_twice_is_refused(stocked: Book) -> None:
    add_delivery(stocked, delivery())
    with pytest.raises(ConflictError):
        add_delivery(stocked, delivery())


def test_a_delivery_against_a_purchase_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_delivery(stocked, delivery(purchase="P-2025-099"))


def test_a_haulier_who_is_not_in_the_register_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_delivery(stocked, delivery(haulier="NOBODY"))


def test_a_delivery_starts_unsampled(stocked: Book) -> None:
    add_delivery(stocked, delivery())
    assert not get_delivery(stocked, "W-24188").sampled
    assert [item.ticket for item in unsampled(stocked)] == ["W-24188"]


def test_attaching_a_sample_takes_it_off_the_list(stocked: Book) -> None:
    add_delivery(stocked, delivery())
    attach_sample(stocked, "W-24188", sample(stocked))
    assert get_delivery(stocked, "W-24188").sample == "B-2025-0918-03"
    assert unsampled(stocked) == ()


def test_a_sample_cannot_be_moved(stocked: Book) -> None:
    """A second sample off one lorry is a retest, and a retest is its own analysis."""
    add_delivery(stocked, delivery())
    attach_sample(stocked, "W-24188", sample(stocked))
    save_analysis(
        stocked,
        analysis_of("B-RETEST", Material.BARLEY, ARRIVED, [Result("moisture", 12.6)]),
    )
    with pytest.raises(ConflictError, match="already sampled"):
        attach_sample(stocked, "W-24188", "B-RETEST")


def test_a_sample_that_is_not_an_analysis_is_refused(stocked: Book) -> None:
    add_delivery(stocked, delivery())
    with pytest.raises(ConflictError, match="does not hold"):
        attach_sample(stocked, "W-24188", "B-NOTHING")


def test_sampling_a_delivery_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        attach_sample(stocked, "W-99999", "B-1")


def test_the_listing_is_oldest_first(stocked: Book) -> None:
    add_delivery(stocked, delivery("W-2", arrived=dt.date(2025, 9, 20)))
    add_delivery(stocked, delivery("W-1", arrived=dt.date(2025, 9, 18)))
    assert [item.ticket for item in list_deliveries(stocked)] == ["W-1", "W-2"]


def test_the_listing_narrows_four_ways(stocked: Book) -> None:
    add_delivery(stocked, delivery("W-1", arrived=dt.date(2025, 9, 18)))
    add_delivery(stocked, delivery("W-2", arrived=dt.date(2025, 9, 25), party="WYKE"))
    assert [item.ticket for item in list_deliveries(stocked, party="WYKE")] == ["W-2"]
    assert [item.ticket for item in list_deliveries(stocked, purchase="P-2025-014")] == [
        "W-1",
        "W-2",
    ]
    narrowed = list_deliveries(stocked, since=dt.date(2025, 9, 20), until=dt.date(2025, 9, 30))
    assert [item.ticket for item in narrowed] == ["W-2"]


def test_the_unsampled_list_can_stop_at_a_day(stocked: Book) -> None:
    """Loads that arrived this afternoon are not yet late for a sample."""
    add_delivery(stocked, delivery("W-1", arrived=dt.date(2025, 9, 18)))
    add_delivery(stocked, delivery("W-2", arrived=dt.date(2025, 9, 25)))
    assert [item.ticket for item in unsampled(stocked, until=dt.date(2025, 9, 20))] == ["W-1"]


def test_an_empty_book_has_nothing_waiting(stocked: Book) -> None:
    assert unsampled(stocked) == ()
    assert list_deliveries(stocked) == ()
