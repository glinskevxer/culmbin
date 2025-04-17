"""Purchases and deliveries."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import ValidationError
from culmbin.model.intake import MAX_VEHICLE_TONNES, Delivery, Purchase
from culmbin.units.season import Window

WINDOW = Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30))


def purchase(code: str = "P-2025-014", **kwargs: object) -> Purchase:
    fields: dict[str, object] = {
        "party": "HOLB",
        "variety": "LAUR",
        "crop_year": 2025,
        "tonnes": 480.0,
        "window": WINDOW,
        "standard": "malting 2025",
        "price_per_tonne": Decimal("232.50"),
        "signed": dt.date(2025, 3, 12),
    }
    fields.update(kwargs)
    return Purchase(code=code, **fields)  # type: ignore[arg-type]


def delivery(ticket: str = "W-24188", **kwargs: object) -> Delivery:
    fields: dict[str, object] = {
        "purchase": "P-2025-014",
        "party": "HOLB",
        "arrived": dt.date(2025, 9, 18),
        "gross_kg": 43_820.0,
        "tare_kg": 15_640.0,
    }
    fields.update(kwargs)
    return Delivery(ticket=ticket, **fields)  # type: ignore[arg-type]


def test_a_purchase_needs_a_code_and_a_standard() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        purchase(" ")
    with pytest.raises(ValidationError, match="no quality standard"):
        purchase(standard="  ")


def test_a_purchase_for_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="0.0 tonnes"):
        purchase(tonnes=0.0)


def test_a_purchase_at_no_price_is_refused() -> None:
    with pytest.raises(ValidationError, match="price of"):
        purchase(price_per_tonne=Decimal("0"))


def test_a_window_before_the_crop_year_is_refused() -> None:
    """A 2025 crop cannot be delivered in May 2025, and the two years catch it."""
    with pytest.raises(ValidationError, match="before crop year"):
        purchase(window=Window(dt.date(2025, 5, 1), dt.date(2025, 6, 30)))


def test_a_window_inside_the_crop_year_is_fine() -> None:
    assert purchase(window=Window(dt.date(2025, 7, 5), dt.date(2025, 8, 30))).crop_year == 2025


def test_a_purchase_is_worth_price_times_tonnes() -> None:
    assert purchase().value == Decimal("111600.00")


def test_a_purchase_knows_its_window() -> None:
    assert purchase().takes_delivery_on(dt.date(2025, 9, 18))
    assert not purchase().takes_delivery_on(dt.date(2025, 12, 1))


def test_a_delivery_nets_off_the_tare() -> None:
    assert delivery().net_kg == pytest.approx(28_180.0)
    assert delivery().net_tonnes == pytest.approx(28.18)


def test_a_delivery_prints_as_a_ticket_and_a_weight() -> None:
    assert str(delivery()) == "W-24188 28.18t on 2025-09-18"


def test_a_delivery_needs_a_ticket_number() -> None:
    with pytest.raises(ValidationError, match="ticket number"):
        delivery("  ")


def test_a_tare_over_the_gross_is_refused() -> None:
    with pytest.raises(ValidationError, match="tares at"):
        delivery(tare_kg=44_000.0)


def test_a_weight_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="weight of nothing"):
        delivery(gross_kg=0.0)


def test_a_load_no_lorry_could_carry_is_refused() -> None:
    """A decimal point in the wrong place is the usual cause of this."""
    with pytest.raises(ValidationError, match="tonne check"):
        delivery(gross_kg=438_200.0, tare_kg=15_640.0)


def test_the_check_is_where_the_constant_says() -> None:
    assert MAX_VEHICLE_TONNES == 32.0


def test_a_delivery_starts_unsampled() -> None:
    assert not delivery().sampled
    assert delivery().sample is None


def test_a_sample_reference_goes_on_without_changing_anything_else() -> None:
    sampled = delivery().with_sample("B-2025-0918-03")
    assert sampled.sampled
    assert sampled.sample == "B-2025-0918-03"
    assert sampled.net_tonnes == delivery().net_tonnes
    assert not delivery().sampled


def test_a_blank_sample_reference_is_refused() -> None:
    with pytest.raises(ValidationError, match="blank sample reference"):
        delivery().with_sample("  ")
