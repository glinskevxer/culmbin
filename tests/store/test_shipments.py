"""Shipments in the book."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import ContractState, ShipmentState
from culmbin.model.sales import Contract, Shipment
from culmbin.store.book import Book
from culmbin.store.contracts import add_contract
from culmbin.store.shipments import (
    add_shipment,
    advance,
    find_shipment,
    get_shipment,
    list_shipments,
    loading_diary,
    reweigh,
    shipped_from_lot,
)
from culmbin.units.season import Window

SIGNED = dt.date(2025, 6, 2)
WINDOW = Window(dt.date(2025, 10, 1), dt.date(2026, 9, 30))
DESPATCHED = dt.date(2025, 11, 20)


def shipment(code: str = "S-2025-0881", **kwargs: object) -> Shipment:
    fields: dict[str, object] = {
        "contract": "C-2025-031",
        "lot": "L-1",
        "tonnes": 28.0,
        "moisture": 4.2,
        "despatched": DESPATCHED,
        "state": ShipmentState.PLANNED,
    }
    fields.update(kwargs)
    return Shipment(code=code, **fields)  # type: ignore[arg-type]


@pytest.fixture
def selling(stocked: Book) -> Book:
    stocked.execute(
        "INSERT INTO malt_bin (code, capacity_tonnes, state) VALUES ('B04', 220.0, 'sealed')"
    )
    stocked.execute(
        "INSERT INTO malt_lot (code, malt_bin, sealed, tonnes, moisture) "
        "VALUES ('L-1', 'B04', '2025-11-12', 200.0, 4.2)"
    )
    add_contract(
        stocked,
        Contract(
            code="C-2025-031",
            customer="BRWY",
            specification="lager 2025",
            tonnes=2400.0,
            moisture=4.5,
            price_per_tonne=Decimal("398.00"),
            window=WINDOW,
            signed=SIGNED,
            state=ContractState.SIGNED,
        ),
    )
    return stocked


def test_a_shipment_reads_back_the_way_it_went_in(selling: Book) -> None:
    add_shipment(selling, shipment())
    assert get_shipment(selling, "S-2025-0881") == shipment()


def test_a_shipment_that_is_not_there_says_which_one(selling: Book) -> None:
    with pytest.raises(NotFoundError, match="S-9"):
        get_shipment(selling, "S-9")
    assert find_shipment(selling, "S-9") is None


def test_a_shipment_against_a_lot_that_is_not_there_is_refused(selling: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_shipment(selling, shipment(lot="L-NOTHING"))


def test_a_shipment_goes_planned_loaded_despatched(selling: Book) -> None:
    add_shipment(selling, shipment())
    assert advance(selling, "S-2025-0881", ShipmentState.LOADED).counts
    assert advance(selling, "S-2025-0881", ShipmentState.DESPATCHED).gone


def test_a_shipment_does_not_skip_loading(selling: Book) -> None:
    add_shipment(selling, shipment())
    with pytest.raises(StateError, match="cannot go to despatched"):
        advance(selling, "S-2025-0881", ShipmentState.DESPATCHED)


def test_a_despatched_shipment_does_not_change_again(selling: Book) -> None:
    """The lorry has gone, and unpicking it takes malt off the customer."""
    add_shipment(selling, shipment(state=ShipmentState.DESPATCHED))
    with pytest.raises(StateError, match="does not change again"):
        advance(selling, "S-2025-0881", ShipmentState.CANCELLED)


def test_a_cancelled_shipment_does_not_come_back(selling: Book) -> None:
    add_shipment(selling, shipment())
    advance(selling, "S-2025-0881", ShipmentState.CANCELLED)
    with pytest.raises(StateError, match="does not change again"):
        advance(selling, "S-2025-0881", ShipmentState.LOADED)


def test_a_planned_shipment_can_be_cancelled(selling: Book) -> None:
    add_shipment(selling, shipment())
    assert not advance(selling, "S-2025-0881", ShipmentState.CANCELLED).counts


def test_a_loaded_shipment_can_still_be_cancelled(selling: Book) -> None:
    """It is malt in a tanker in the yard, and it can be tipped back."""
    add_shipment(selling, shipment(state=ShipmentState.LOADED))
    assert not advance(selling, "S-2025-0881", ShipmentState.CANCELLED).counts


def test_reweighing_takes_the_real_ticket(selling: Book) -> None:
    add_shipment(selling, shipment(tonnes=28.0))
    reweighed = reweigh(selling, "S-2025-0881", 27.84, 4.3)
    assert reweighed.tonnes == pytest.approx(27.84)
    assert reweighed.moisture == pytest.approx(4.3)


def test_a_despatched_shipment_is_not_reweighed(selling: Book) -> None:
    add_shipment(selling, shipment(state=ShipmentState.DESPATCHED))
    with pytest.raises(StateError, match="is not reweighed"):
        reweigh(selling, "S-2025-0881", 27.84, 4.3)


def test_a_shipment_of_nothing_is_refused(selling: Book) -> None:
    add_shipment(selling, shipment())
    with pytest.raises(ConflictError, match="not a shipment"):
        reweigh(selling, "S-2025-0881", 0.0, 4.3)


def test_reweighing_something_that_is_not_there_is_refused(selling: Book) -> None:
    with pytest.raises(NotFoundError):
        reweigh(selling, "S-9", 27.84, 4.3)


def test_the_listing_narrows_five_ways(selling: Book) -> None:
    add_shipment(selling, shipment("S-1", despatched=dt.date(2025, 11, 18)))
    add_shipment(
        selling, shipment("S-2", despatched=dt.date(2025, 11, 25), state=ShipmentState.LOADED)
    )
    assert [item.code for item in list_shipments(selling)] == ["S-1", "S-2"]
    loaded = list_shipments(selling, state=ShipmentState.LOADED)
    assert [item.code for item in loaded] == ["S-2"]
    assert len(list_shipments(selling, lot="L-1")) == 2
    assert len(list_shipments(selling, contract="C-2025-031")) == 2
    narrowed = list_shipments(selling, since=dt.date(2025, 11, 20))
    assert [item.code for item in narrowed] == ["S-2"]


def test_a_planned_load_still_spoken_for_the_malt(selling: Book) -> None:
    """Allocating twice is how two tankers turn up for the same forty tonnes."""
    add_shipment(selling, shipment("S-1", tonnes=28.0))
    assert shipped_from_lot(selling, "L-1") == pytest.approx(28.0)


def test_a_cancelled_load_gives_the_malt_back(selling: Book) -> None:
    add_shipment(selling, shipment("S-1", tonnes=28.0))
    advance(selling, "S-1", ShipmentState.CANCELLED)
    assert shipped_from_lot(selling, "L-1") == pytest.approx(0.0)


def test_a_lot_nothing_has_come_off_has_nothing_shipped(selling: Book) -> None:
    assert shipped_from_lot(selling, "L-1") == pytest.approx(0.0)


def test_the_loading_diary_is_what_has_not_gone_yet(selling: Book) -> None:
    add_shipment(selling, shipment("S-1", despatched=dt.date(2025, 11, 18)))
    add_shipment(
        selling,
        shipment("S-2", despatched=dt.date(2025, 11, 19), state=ShipmentState.DESPATCHED),
    )
    add_shipment(
        selling, shipment("S-3", despatched=dt.date(2025, 11, 20), state=ShipmentState.LOADED)
    )
    diary = loading_diary(selling, dt.date(2025, 11, 17), dt.date(2025, 11, 21))
    assert [item.code for item in diary] == ["S-1", "S-3"]


def test_an_empty_diary_is_empty(selling: Book) -> None:
    assert loading_diary(selling, dt.date(2025, 11, 17), dt.date(2025, 11, 21)) == ()
