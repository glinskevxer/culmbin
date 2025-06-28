"""Contracts, calls and shipments.

Most of these are about the contract tonne, which is not the weighbridge
tonne and never has been.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import StateError, ValidationError
from culmbin.model.enums import ContractState, ShipmentState
from culmbin.model.sales import Call, Contract, Shipment
from culmbin.units.season import Window

SIGNED = dt.date(2025, 6, 2)
WINDOW = Window(dt.date(2025, 10, 1), dt.date(2026, 9, 30))
DESPATCHED = dt.date(2025, 11, 20)


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


def shipment(code: str = "S-2025-0881", **kwargs: object) -> Shipment:
    fields: dict[str, object] = {
        "contract": "C-2025-031",
        "lot": "L-2025-0412",
        "tonnes": 28.0,
        "moisture": 4.2,
        "despatched": DESPATCHED,
        "state": ShipmentState.DESPATCHED,
    }
    fields.update(kwargs)
    return Shipment(code=code, **fields)  # type: ignore[arg-type]


def test_a_contract_prints_its_customer_and_tonnage() -> None:
    assert str(contract()) == "C-2025-031 BRWY 2400t"
    assert str(contract(variety="LAUR")) == "C-2025-031 BRWY 2400t LAUR"


def test_a_contract_needs_a_code_a_price_and_a_specification() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        contract(" ")
    with pytest.raises(ValidationError, match="price of"):
        contract(price_per_tonne=Decimal("0"))
    with pytest.raises(ValidationError, match="no specification"):
        contract(specification="  ")


def test_a_contract_for_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="0.0 tonnes"):
        contract(tonnes=0.0)


def test_a_contract_written_at_an_impossible_moisture_is_refused() -> None:
    with pytest.raises(ValidationError, match="percent moisture"):
        contract(moisture=20.0)


def test_a_contract_that_opens_before_it_was_signed_is_refused() -> None:
    with pytest.raises(ValidationError, match="was signed later"):
        contract(window=Window(dt.date(2025, 1, 1), dt.date(2025, 12, 31)))


def test_a_contract_is_worth_price_times_tonnes() -> None:
    assert contract().value == Decimal("955200.00")


def test_a_contract_carries_its_dry_tonnage() -> None:
    assert contract().dry_tonnes == pytest.approx(2400.0 * 0.955)


def test_only_a_signed_contract_is_open() -> None:
    assert contract().open
    assert not contract(state=ContractState.DRAFT).open
    assert not contract(state=ContractState.CLOSED).open


def test_a_closed_contract_says_so_when_asked() -> None:
    with pytest.raises(StateError, match="nothing ships against it"):
        contract(state=ContractState.CLOSED).check_open()


def test_an_open_contract_passes_quietly() -> None:
    contract().check_open()


def test_a_contract_naming_a_variety_says_so() -> None:
    assert contract(variety="LAUR").names_a_variety
    assert not contract().names_a_variety


def test_a_contract_knows_its_window() -> None:
    assert contract().takes_shipment_on(DESPATCHED)
    assert not contract().takes_shipment_on(dt.date(2026, 12, 1))


def test_a_call_prints_its_tonnage_and_week() -> None:
    call = Call(
        "K-14", "C-2025-031", 200.0, Window(dt.date(2026, 4, 6), dt.date(2026, 4, 10)), SIGNED
    )
    assert str(call) == "K-14 200t 2026-04-06..2026-04-10"


def test_a_call_needs_a_code_and_a_tonnage() -> None:
    week = Window(dt.date(2026, 4, 6), dt.date(2026, 4, 10))
    with pytest.raises(ValidationError, match="needs a code"):
        Call(" ", "C-1", 200.0, week, SIGNED)
    with pytest.raises(ValidationError, match="calls for"):
        Call("K-1", "C-1", 0.0, week, SIGNED)


def test_a_call_placed_after_the_week_it_wants_is_refused() -> None:
    week = Window(dt.date(2025, 1, 6), dt.date(2025, 1, 10))
    with pytest.raises(ValidationError, match="placed after"):
        Call("K-1", "C-1", 200.0, week, SIGNED)


def test_a_shipment_prints_its_weight_and_moisture() -> None:
    assert str(shipment()) == "S-2025-0881 28.00t at 4.2 on 2025-11-20"


def test_a_shipment_needs_a_code_and_a_weight() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        shipment(" ")
    with pytest.raises(ValidationError, match="is 0.0 tonnes"):
        shipment(tonnes=0.0)


def test_drier_malt_draws_a_contract_down_by_more_than_it_weighs() -> None:
    """28 tonnes at 4.2 against a contract at 4.5 is 28.088 contract tonnes."""
    assert shipment().contract_tonnes(4.5) == pytest.approx(28.0879, rel=1e-4)


def test_wetter_malt_draws_it_down_by_less() -> None:
    assert shipment(moisture=5.0).contract_tonnes(4.5) < 28.0


def test_malt_at_the_contract_moisture_draws_down_what_it_weighs() -> None:
    assert shipment(moisture=4.5).contract_tonnes(4.5) == pytest.approx(28.0)


def test_a_shipment_is_priced_on_the_contract_tonne() -> None:
    """Otherwise a wet load would be worth more than a dry one."""
    dry = shipment(moisture=4.2).value(Decimal("398.00"), 4.5)
    wet = shipment(moisture=5.0).value(Decimal("398.00"), 4.5)
    assert dry > wet


def test_a_shipment_value_is_to_the_penny() -> None:
    assert shipment().value(Decimal("398.00"), 4.5) == Decimal("11179.01")
    assert shipment(moisture=4.5).value(Decimal("398.00"), 4.5) == Decimal("11144.00")


def test_a_planned_shipment_does_not_draw_the_contract_down() -> None:
    """It is a slot in the loading diary and the malt is still in the bin."""
    assert not shipment(state=ShipmentState.PLANNED).counts


def test_a_loaded_shipment_does() -> None:
    assert shipment(state=ShipmentState.LOADED).counts
    assert not shipment(state=ShipmentState.LOADED).gone


def test_a_despatched_shipment_has_gone() -> None:
    assert shipment().gone
    assert shipment().counts


def test_a_cancelled_shipment_counts_for_nothing() -> None:
    assert not shipment(state=ShipmentState.CANCELLED).counts


def test_a_shipment_carries_its_dry_tonnage() -> None:
    assert shipment().dry_tonnes == pytest.approx(28.0 * 0.958)
