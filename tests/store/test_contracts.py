"""Contracts, call-offs and where a contract stands."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import ContractState
from culmbin.model.sales import Call, Contract
from culmbin.store.book import Book
from culmbin.store.contracts import (
    add_call,
    add_contract,
    called_tonnes,
    find_contract,
    get_call,
    get_contract,
    list_calls,
    list_contracts,
    open_contracts_on,
    position,
    set_state,
)
from culmbin.units.season import Window

SIGNED = dt.date(2025, 6, 2)
WINDOW = Window(dt.date(2025, 10, 1), dt.date(2026, 9, 30))
WEEK = Window(dt.date(2026, 4, 6), dt.date(2026, 4, 10))


def contract(code: str = "C-2025-031", **kwargs: object) -> Contract:
    fields: dict[str, object] = {
        "customer": "BRWY",
        "specification": "lager 2025",
        "tonnes": 2400.0,
        "moisture": 4.5,
        "price_per_tonne": Decimal("398.00"),
        "window": WINDOW,
        "signed": SIGNED,
        "state": ContractState.SIGNED,
    }
    fields.update(kwargs)
    return Contract(code=code, **fields)  # type: ignore[arg-type]


def ship(book: Book, code: str, tonnes: float, moisture: float, state: str) -> None:
    """Write a shipment straight in, which is what moves a contract position."""
    book.execute(
        "INSERT INTO malt_lot (code, malt_bin, sealed, tonnes, moisture) "
        "SELECT ?, 'B04', '2025-11-12', 200.0, 4.3 WHERE NOT EXISTS "
        "(SELECT 1 FROM malt_lot WHERE code = ?)",
        ("L-1", "L-1"),
    )
    book.execute(
        "INSERT INTO shipment (code, contract, lot, tonnes, moisture, despatched, state) "
        "VALUES (?, 'C-2025-031', 'L-1', ?, ?, '2025-11-20', ?)",
        (code, tonnes, moisture, state),
    )


@pytest.fixture
def selling(stocked: Book) -> Book:
    stocked.execute(
        "INSERT INTO malt_bin (code, capacity_tonnes, state) VALUES ('B04', 220.0, 'sealed')"
    )
    add_contract(stocked, contract())
    return stocked


def test_a_contract_reads_back_the_way_it_went_in(selling: Book) -> None:
    assert get_contract(selling, "C-2025-031") == contract()


def test_the_price_comes_back_as_a_decimal(selling: Book) -> None:
    assert get_contract(selling, "C-2025-031").price_per_tonne == Decimal("398.00")


def test_a_contract_that_is_not_there_says_which_one(selling: Book) -> None:
    with pytest.raises(NotFoundError, match="C-9"):
        get_contract(selling, "C-9")
    assert find_contract(selling, "C-9") is None


def test_a_contract_on_a_specification_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_contract(stocked, contract(specification="nothing"))


def test_a_contract_naming_a_variety_that_is_not_listed_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_contract(stocked, contract(variety="NOPE"))


def test_a_contract_moves_from_draft_to_signed(stocked: Book) -> None:
    add_contract(stocked, contract(state=ContractState.DRAFT))
    assert set_state(stocked, "C-2025-031", ContractState.SIGNED).open


def test_a_closed_contract_does_not_reopen(selling: Book) -> None:
    """Reopening one lets malt ship against a contract the customer thinks is done."""
    set_state(selling, "C-2025-031", ContractState.CLOSED)
    with pytest.raises(StateError, match="does not reopen"):
        set_state(selling, "C-2025-031", ContractState.SIGNED)


def test_setting_the_state_it_is_already_in_is_refused(selling: Book) -> None:
    with pytest.raises(ConflictError, match="already signed"):
        set_state(selling, "C-2025-031", ContractState.SIGNED)


def test_the_listing_narrows_by_customer_and_state(selling: Book) -> None:
    add_contract(selling, contract("C-2025-032", state=ContractState.DRAFT))
    assert len(list_contracts(selling)) == 2
    assert [item.code for item in list_contracts(selling, customer="BRWY")] == [
        "C-2025-031",
        "C-2025-032",
    ]
    signed = list_contracts(selling, state=ContractState.SIGNED)
    assert [item.code for item in signed] == ["C-2025-031"]


def test_open_contracts_are_the_signed_ones_in_window(selling: Book) -> None:
    assert [item.code for item in open_contracts_on(selling, dt.date(2026, 4, 8))] == ["C-2025-031"]
    assert open_contracts_on(selling, dt.date(2027, 4, 8)) == ()


def test_a_call_reads_back_the_way_it_went_in(selling: Book) -> None:
    call = Call("K-14", "C-2025-031", 200.0, WEEK, SIGNED)
    add_call(selling, call)
    assert get_call(selling, "K-14") == call


def test_a_call_against_a_draft_contract_is_refused(stocked: Book) -> None:
    add_contract(stocked, contract(state=ContractState.DRAFT))
    with pytest.raises(StateError, match="nothing ships against it"):
        add_call(stocked, Call("K-1", "C-2025-031", 200.0, WEEK, SIGNED))


def test_a_call_outside_the_contract_window_is_refused(selling: Book) -> None:
    outside = Window(dt.date(2027, 4, 6), dt.date(2027, 4, 10))
    with pytest.raises(ConflictError, match="runs 2025-10-01"):
        add_call(selling, Call("K-1", "C-2025-031", 200.0, outside, SIGNED))


def test_calls_past_the_contract_tonnage_are_refused(selling: Book) -> None:
    add_call(selling, Call("K-1", "C-2025-031", 2000.0, WEEK, SIGNED))
    with pytest.raises(ConflictError, match="against 2400.0t"):
        add_call(selling, Call("K-2", "C-2025-031", 500.0, WEEK, SIGNED))


def test_called_tonnes_add_up(selling: Book) -> None:
    add_call(selling, Call("K-1", "C-2025-031", 200.0, WEEK, SIGNED))
    add_call(selling, Call("K-2", "C-2025-031", 300.0, WEEK, SIGNED))
    assert called_tonnes(selling, "C-2025-031") == pytest.approx(500.0)


def test_a_contract_with_no_calls_has_none(selling: Book) -> None:
    assert called_tonnes(selling, "C-2025-031") == pytest.approx(0.0)
    assert list_calls(selling) == ()


def test_calls_list_by_week_and_by_contract(selling: Book) -> None:
    later = Window(dt.date(2026, 5, 4), dt.date(2026, 5, 8))
    add_call(selling, Call("K-2", "C-2025-031", 200.0, later, SIGNED))
    add_call(selling, Call("K-1", "C-2025-031", 200.0, WEEK, SIGNED))
    assert [item.code for item in list_calls(selling)] == ["K-1", "K-2"]
    in_april = list_calls(selling, window=Window(dt.date(2026, 4, 1), dt.date(2026, 4, 30)))
    assert [item.code for item in in_april] == ["K-1"]


def test_a_call_that_is_not_there_says_which_one(selling: Book) -> None:
    with pytest.raises(NotFoundError, match="K-9"):
        get_call(selling, "K-9")


def test_a_contract_with_nothing_shipped_is_all_outstanding(selling: Book) -> None:
    where = position(selling, "C-2025-031")
    assert where.delivered == pytest.approx(0.0)
    assert where.outstanding == pytest.approx(2400.0)
    assert not where.complete


def test_a_despatched_load_draws_the_contract_down(selling: Book) -> None:
    ship(selling, "S-1", 28.0, 4.2, "despatched")
    where = position(selling, "C-2025-031")
    assert where.delivered == pytest.approx(28.088, rel=1e-4)
    assert where.outstanding < 2372.0


def test_a_planned_load_is_committed_and_not_delivered(selling: Book) -> None:
    """It is a slot in the loading diary and the malt is still in the bin."""
    ship(selling, "S-1", 28.0, 4.5, "planned")
    where = position(selling, "C-2025-031")
    assert where.delivered == pytest.approx(0.0)
    assert where.committed == pytest.approx(28.0)
    assert where.uncommitted == pytest.approx(2372.0)


def test_a_loaded_load_counts_as_delivered(selling: Book) -> None:
    ship(selling, "S-1", 28.0, 4.5, "loaded")
    assert position(selling, "C-2025-031").delivered == pytest.approx(28.0)


def test_a_cancelled_load_counts_for_nothing(selling: Book) -> None:
    ship(selling, "S-1", 28.0, 4.5, "cancelled")
    where = position(selling, "C-2025-031")
    assert where.delivered == pytest.approx(0.0)
    assert where.committed == pytest.approx(0.0)


def test_an_over_shipped_contract_has_nothing_left_rather_than_less(selling: Book) -> None:
    ship(selling, "S-1", 30.0, 4.5, "despatched")
    add_contract(selling, contract("C-SMALL", tonnes=20.0))
    selling.execute("UPDATE shipment SET contract = 'C-SMALL' WHERE code = 'S-1'")
    where = position(selling, "C-SMALL")
    assert where.outstanding == pytest.approx(0.0)
    assert where.complete
    assert where.percent_delivered > 100.0


def test_a_contract_of_nothing_reports_no_progress(selling: Book) -> None:
    where = position(selling, "C-2025-031")
    assert where.percent_delivered == pytest.approx(0.0)
