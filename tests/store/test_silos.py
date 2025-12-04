"""Barley silos in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.intake.desk import grade_load, take_sample, weigh_in
from culmbin.model.intake import Delivery
from culmbin.model.silo import Silo
from culmbin.store.book import Book
from culmbin.store.pieces import record_source
from culmbin.store.silos import (
    add_silo,
    find_silo,
    get_silo,
    holding_in,
    list_silos,
    silo_holding,
    sweep,
    tip,
    untipped,
)
from tests.support.records import kilned
from tests.support.samples import barley_sample

ARRIVED = dt.date(2025, 9, 18)
GRADED = dt.date(2025, 9, 19)
TIPPED = dt.date(2025, 9, 19)


def lorry(stocked: Book, ticket: str, purchase: str = "P-2025-014", **overrides: float) -> str:
    """A lorry taken in, sampled and graded."""
    weigh_in(
        stocked,
        Delivery(
            ticket=ticket,
            purchase=purchase,
            party="HOLB",
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
            harvested=dt.date(2025, 8, 14),
        ),
    )
    take_sample(stocked, ticket, barley_sample(f"B-{ticket}", ARRIVED, **overrides))
    grade_load(stocked, ticket, GRADED)
    return ticket


def test_a_silo_reads_back_the_way_it_went_in(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    assert get_silo(stocked, "SL1") == Silo("SL1", 400.0)
    assert [item.code for item in list_silos(stocked)] == ["SL1"]


def test_a_silo_that_is_not_there_says_which_one(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="SL9"):
        get_silo(stocked, "SL9")
    assert find_silo(stocked, "SL9") is None


def test_an_empty_silo_holds_nothing(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    assert holding_in(stocked, "SL1").empty


def test_the_settled_tonnage_goes_in_and_not_the_lorry_weight(stocked: Book) -> None:
    """The screenings went in a different bin and the water is not barley."""
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1", moisture=15.0, screenings=3.4)
    tip(stocked, "SL1", "W-1", TIPPED)
    held = holding_in(stocked, "SL1")
    assert held.tonnes < 28.18
    assert held.tonnes > 26.0


def test_a_clean_load_goes_in_whole(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1")
    tip(stocked, "SL1", "W-1", TIPPED)
    assert holding_in(stocked, "SL1").tonnes == pytest.approx(28.18)


def test_a_rejected_load_does_not_go_in(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1", germ_capacity=90.0)
    with pytest.raises(StateError, match="back down the road"):
        tip(stocked, "SL1", "W-1", TIPPED)


def test_an_ungraded_load_does_not_go_in(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    weigh_in(
        stocked,
        Delivery(
            ticket="W-9",
            purchase="P-2025-014",
            party="HOLB",
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
        ),
    )
    with pytest.raises(StateError, match="has not been graded"):
        tip(stocked, "SL1", "W-9", TIPPED)


def test_a_load_cannot_be_tipped_twice(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    add_silo(stocked, Silo("SL2", 400.0))
    lorry(stocked, "W-1")
    tip(stocked, "SL1", "W-1", TIPPED)
    with pytest.raises(ConflictError):
        tip(stocked, "SL2", "W-1", TIPPED)


def test_more_than_the_silo_takes_is_refused(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 30.0))
    lorry(stocked, "W-1")
    lorry(stocked, "W-2")
    tip(stocked, "SL1", "W-1", TIPPED)
    with pytest.raises(ConflictError, match="against a capacity"):
        tip(stocked, "SL1", "W-2", TIPPED)


def test_two_loads_of_one_variety_leave_the_silo_clean(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1")
    lorry(stocked, "W-2")
    tip(stocked, "SL1", "W-1", TIPPED)
    tip(stocked, "SL1", "W-2", TIPPED)
    assert not get_silo(stocked, "SL1").mixed
    assert holding_in(stocked, "SL1").variety == "LAUR"


def test_a_second_variety_marks_the_silo(stocked: Book) -> None:
    stocked.execute(
        "INSERT INTO purchase (code, party, variety, crop_year, tonnes, window_start, "
        "window_end, standard, price_per_tonne, signed) VALUES "
        "('P-DIAB', 'HOLB', 'DIAB', 2025, 300.0, '2025-09-01', '2025-11-30', "
        "'malting 2025', '228.00', '2025-03-20')"
    )
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1")
    lorry(stocked, "W-2", purchase="P-DIAB")
    tip(stocked, "SL1", "W-1", TIPPED)
    tip(stocked, "SL1", "W-2", TIPPED)
    assert get_silo(stocked, "SL1").mixed
    assert holding_in(stocked, "SL1").variety is None


def test_the_moisture_averages_over_what_went_in(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1", moisture=12.0)
    lorry(stocked, "W-2", moisture=14.0)
    tip(stocked, "SL1", "W-1", TIPPED)
    tip(stocked, "SL1", "W-2", TIPPED)
    assert 12.0 < holding_in(stocked, "SL1").moisture < 14.0


def test_charging_a_piece_takes_it_out_of_the_silo(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1")
    tip(stocked, "SL1", "W-1", TIPPED)
    kilned(stocked, "2025-118")
    record_source(stocked, "2025-118", "W-1", 20.0)
    assert holding_in(stocked, "SL1").tonnes == pytest.approx(8.18)


def test_a_load_drawn_right_out_leaves_the_silo(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1")
    tip(stocked, "SL1", "W-1", TIPPED)
    kilned(stocked, "2025-118")
    record_source(stocked, "2025-118", "W-1", 28.18)
    assert holding_in(stocked, "SL1").empty


def test_a_silo_says_where_a_load_went(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1")
    tip(stocked, "SL1", "W-1", TIPPED)
    assert silo_holding(stocked, "W-1") == "SL1"


def test_a_load_nobody_tipped_is_nowhere(stocked: Book) -> None:
    lorry(stocked, "W-1")
    assert silo_holding(stocked, "W-1") is None


def test_an_accepted_load_nobody_tipped_is_still_in_the_pit(stocked: Book) -> None:
    """The pit is where barley goes bad, so the list is worth having."""
    lorry(stocked, "W-1")
    assert untipped(stocked) == ("W-1",)


def test_a_tipped_load_is_off_the_pit_list(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1")
    tip(stocked, "SL1", "W-1", TIPPED)
    assert untipped(stocked) == ()


def test_a_rejected_load_is_not_on_the_pit_list(stocked: Book) -> None:
    lorry(stocked, "W-1", germ_capacity=90.0)
    assert untipped(stocked) == ()


def test_sweeping_an_empty_silo_clears_the_mark(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0, mixed=True))
    assert not sweep(stocked, "SL1").mixed


def test_a_silo_with_barley_in_it_cannot_be_swept(stocked: Book) -> None:
    add_silo(stocked, Silo("SL1", 400.0))
    lorry(stocked, "W-1")
    tip(stocked, "SL1", "W-1", TIPPED)
    with pytest.raises(StateError, match="cannot be swept"):
        sweep(stocked, "SL1")


def test_a_holding_of_a_silo_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        holding_in(stocked, "SL9")
