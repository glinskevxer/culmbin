"""The sales desk, end to end.

The four checks in `allocate` are the point of this file, and each one has a
test that fails on that check alone with the other three satisfied.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import ConflictError, NotFoundError, SegregationError, StateError
from culmbin.model.enums import ContractState, ShipmentState
from culmbin.model.sales import Call, Contract
from culmbin.sales.desk import (
    allocate,
    assess_lot,
    availability,
    cancel,
    customer_book,
    despatch,
    load,
    shipped_in,
)
from culmbin.store.bins import contents_of
from culmbin.store.book import Book
from culmbin.store.contracts import add_call, add_contract, position, set_state
from culmbin.store.lots import get_lot
from culmbin.store.shipments import get_shipment
from culmbin.units.season import Window
from tests.support.books import CONTRACT_WINDOW as WINDOW
from tests.support.books import SIGNED, a_lot

ON = dt.date(2025, 11, 20)
WEEK = Window(dt.date(2025, 11, 17), dt.date(2025, 11, 21))


def test_a_clean_lot_goes_out_against_a_contract(desk: Book) -> None:
    shipment = allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    assert shipment.state is ShipmentState.PLANNED
    assert shipment.moisture == pytest.approx(get_lot(desk, "L-CLEAN").moisture)


def test_a_lot_with_no_analysis_cannot_go(desk: Book) -> None:
    desk.execute("UPDATE malt_lot SET analysis = NULL WHERE code = 'L-CLEAN'")
    with pytest.raises(StateError, match="cannot be shipped"):
        allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)


def test_a_lot_outside_the_specification_cannot_go(desk: Book) -> None:
    a_lot(desk, "L-DARK", "B05", ("LAUR",), "M-DARK", colour=6.2)
    with pytest.raises(ConflictError, match="is 6.20 on colour"):
        allocate(desk, "S-1", "C-2025-031", "L-DARK", 28.0, ON)


def test_the_refusal_quotes_the_clause_the_customer_wrote(desk: Book) -> None:
    a_lot(desk, "L-DARK", "B05", ("LAUR",), "M-DARK", colour=6.2)
    with pytest.raises(ConflictError, match="colour 2.5 to 4.5 EBC"):
        allocate(desk, "S-1", "C-2025-031", "L-DARK", 28.0, ON)


def test_a_lot_missing_a_clause_result_cannot_go(desk: Book) -> None:
    """Untested is not a pass, and the message says which clause nobody ran."""
    desk.execute("DELETE FROM result WHERE analysis = 'M-CLEAN' AND code = 'colour'")
    with pytest.raises(ConflictError, match="has no colour result"):
        allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)


def test_a_mixed_lot_cannot_serve_a_contract_naming_a_variety(desk: Book) -> None:
    """The analysis has nothing to say about this and never had."""
    a_lot(desk, "L-MIXED", "B05", ("LAUR", "DIAB"), "M-MIXED")
    add_contract(
        desk,
        Contract(
            code="C-VARIETY",
            customer="BRWY",
            specification="lager 2025",
            tonnes=500.0,
            moisture=4.5,
            price_per_tonne=Decimal("410.00"),
            window=WINDOW,
            signed=SIGNED,
            state=ContractState.SIGNED,
            variety="LAUR",
        ),
    )
    with pytest.raises(SegregationError, match="no variety to declare"):
        allocate(desk, "S-1", "C-VARIETY", "L-MIXED", 28.0, ON)


def test_a_clean_lot_of_the_wrong_variety_cannot_serve_it_either(desk: Book) -> None:
    a_lot(desk, "L-DIAB", "B05", ("DIAB",), "M-DIAB")
    add_contract(
        desk,
        Contract(
            code="C-VARIETY",
            customer="BRWY",
            specification="lager 2025",
            tonnes=500.0,
            moisture=4.5,
            price_per_tonne=Decimal("410.00"),
            window=WINDOW,
            signed=SIGNED,
            state=ContractState.SIGNED,
            variety="LAUR",
        ),
    )
    with pytest.raises(SegregationError, match="contract wants LAUR"):
        allocate(desk, "S-1", "C-VARIETY", "L-DIAB", 28.0, ON)


def test_more_than_the_lot_has_left_cannot_be_allocated(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 40.0, ON)
    with pytest.raises(ConflictError, match="20.00t free"):
        allocate(desk, "S-2", "C-2025-031", "L-CLEAN", 28.0, ON)


def test_a_planned_load_holds_the_malt(desk: Book) -> None:
    """Allocating twice is how two tankers turn up for the same forty tonnes."""
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 40.0, ON)
    assert availability(desk, "L-CLEAN").free_tonnes == pytest.approx(20.0)


def test_cancelling_gives_the_malt_back(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 40.0, ON)
    cancel(desk, "S-1")
    assert availability(desk, "L-CLEAN").free_tonnes == pytest.approx(60.0)


def test_a_draft_contract_takes_nothing(desk: Book) -> None:
    set_state(desk, "C-2025-031", ContractState.CLOSED)
    with pytest.raises(StateError, match="nothing ships against it"):
        allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)


def test_a_load_outside_the_contract_window_is_refused(desk: Book) -> None:
    with pytest.raises(ConflictError, match="runs 2025-10-01"):
        allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, dt.date(2027, 1, 4))


def test_a_call_against_another_contract_is_refused(desk: Book) -> None:
    add_contract(
        desk,
        Contract(
            code="C-OTHER",
            customer="BRWY",
            specification="lager 2025",
            tonnes=500.0,
            moisture=4.5,
            price_per_tonne=Decimal("410.00"),
            window=WINDOW,
            signed=SIGNED,
            state=ContractState.SIGNED,
        ),
    )
    add_call(desk, Call("K-1", "C-OTHER", 200.0, WEEK, SIGNED))
    with pytest.raises(ConflictError, match="is against C-OTHER"):
        allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON, call="K-1")


def test_a_call_on_the_same_contract_goes_on_the_shipment(desk: Book) -> None:
    add_call(desk, Call("K-1", "C-2025-031", 200.0, WEEK, SIGNED))
    shipment = allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON, call="K-1")
    assert shipment.call == "K-1"


def test_a_lot_that_is_not_there_is_refused(desk: Book) -> None:
    with pytest.raises(NotFoundError):
        allocate(desk, "S-1", "C-2025-031", "L-NOTHING", 28.0, ON)


def test_loading_takes_the_weighbridge_figure_and_empties_the_bin(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    loaded = load(desk, "S-1", 27.84, 4.3, ON)
    assert loaded.tonnes == pytest.approx(27.84)
    assert contents_of(desk, "B04").tonnes == pytest.approx(60.0 - 27.84)


def test_only_a_planned_load_is_weighed(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    load(desk, "S-1", 27.84, 4.3, ON)
    with pytest.raises(StateError, match="only a planned load"):
        load(desk, "S-1", 27.84, 4.3, ON)


def test_a_failed_load_leaves_the_bin_alone(desk: Book) -> None:
    """The bin issue and the state change land together or not at all."""
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    with pytest.raises(ConflictError):
        load(desk, "S-1", 900.0, 4.3, ON)
    assert contents_of(desk, "B04").tonnes == pytest.approx(60.0)
    assert get_shipment(desk, "S-1").state is ShipmentState.PLANNED


def test_despatching_draws_the_contract_down(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    load(desk, "S-1", 28.0, 4.2, ON)
    despatch(desk, "S-1")
    assert position(desk, "C-2025-031").delivered == pytest.approx(28.088, rel=1e-4)


def test_a_lot_can_be_assessed_on_its_own(desk: Book) -> None:
    assert assess_lot(desk, "L-CLEAN", "lager 2025").met


def test_an_uncertified_lot_cannot_be_assessed(desk: Book) -> None:
    desk.execute("UPDATE malt_lot SET analysis = NULL WHERE code = 'L-CLEAN'")
    with pytest.raises(StateError, match="cannot be assessed"):
        assess_lot(desk, "L-CLEAN", "lager 2025")


def test_the_customer_book_says_what_is_left_on_each_contract(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    load(desk, "S-1", 28.0, 4.5, ON)
    despatch(desk, "S-1")
    entries = customer_book(desk, "BRWY")
    assert [contract.code for contract, _ in entries] == ["C-2025-031"]
    assert entries[0][1] == pytest.approx(2372.0)


def test_a_customer_with_nothing_has_an_empty_book(desk: Book) -> None:
    assert customer_book(desk, "NOBODY") == ()


def test_what_shipped_in_a_week_is_what_actually_left(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    load(desk, "S-1", 28.0, 4.2, ON)
    assert shipped_in(desk, WEEK) == ()
    despatch(desk, "S-1")
    assert [item.code for item in shipped_in(desk, WEEK)] == ["S-1"]


def test_an_empty_lot_says_so(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 60.0, ON)
    assert availability(desk, "L-CLEAN").empty
