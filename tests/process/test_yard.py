"""Charging a piece out of a silo, which is where the traceability starts."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import SegregationError, StateError
from culmbin.intake.desk import grade_load, take_sample, weigh_in
from culmbin.model.enums import MaltStyle, Role
from culmbin.model.intake import Delivery, Purchase
from culmbin.model.party import Party
from culmbin.model.silo import Silo
from culmbin.process.yard import charge_from_silo, check_can_charge, plan_charge, silo_for
from culmbin.store.book import Book
from culmbin.store.parties import add_party
from culmbin.store.pieces import get_piece, sources_of
from culmbin.store.purchases import add_purchase
from culmbin.store.silos import add_silo, holding_in, tip
from culmbin.units.season import Window
from tests.support.samples import barley_sample

ARRIVED = dt.date(2025, 9, 18)
CHARGED = dt.date(2025, 11, 3)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


@pytest.fixture
def yard(plant: Book) -> Book:
    """A grower, two purchases, a silo and nothing tipped yet."""
    add_party(
        plant, Party("HOLB", "Holbeach Grange", Role.GROWER, dt.date(2011, 6, 1), holding="12/345")
    )
    from culmbin.intake.standard import Standard
    from culmbin.store.standards import find_standard

    if find_standard(plant, "malting 2025") is None:  # pragma: no cover
        from culmbin.store.standards import add_standard

        add_standard(plant, Standard("malting 2025"))
    for code, variety in (("P-LAUR", "LAUR"), ("P-DIAB", "DIAB")):
        add_purchase(
            plant,
            Purchase(
                code=code,
                party="HOLB",
                variety=variety,
                crop_year=2025,
                tonnes=480.0,
                window=Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30)),
                standard="malting 2025",
                price_per_tonne=Decimal("232.50"),
                signed=dt.date(2025, 3, 12),
            ),
        )
    add_silo(plant, Silo("SL1", 400.0))
    add_silo(plant, Silo("SL2", 400.0))
    return plant


def lorry(yard: Book, ticket: str, purchase: str = "P-LAUR", **overrides: float) -> str:
    weigh_in(
        yard,
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
    take_sample(yard, ticket, barley_sample(f"B-{ticket}", ARRIVED, **overrides))
    grade_load(yard, ticket, dt.date(2025, 9, 19))
    return ticket


def stocked_silo(yard: Book, silo: str = "SL1", *tickets: str) -> None:
    for ticket in tickets or ("W-1", "W-2"):
        lorry(yard, ticket)
        tip(yard, silo, ticket, dt.date(2025, 9, 19))


def charge(yard: Book, tonnes: float = 40.0, code: str = "2025-118") -> None:
    charge_from_silo(
        yard,
        code,
        "SL1",
        "LAUR",
        2025,
        MaltStyle.PALE_ALE,
        tonnes,
        "S1",
        CHARGED,
        PROGRAMME,
        SCHEDULE,
        CURVE,
    )


def test_a_charge_carries_a_share_of_every_load(yard: Book) -> None:
    stocked_silo(yard)
    charge(yard)
    sources = dict(sources_of(yard, "2025-118"))
    assert set(sources) == {"W-1", "W-2"}
    assert sum(sources.values()) == pytest.approx(40.0)


def test_the_moisture_comes_off_the_silo_and_is_not_typed(yard: Book) -> None:
    """A typed moisture and a silo moisture that disagree cannot be settled."""
    stocked_silo(yard)
    before = holding_in(yard, "SL1").moisture
    charge(yard)
    assert get_piece(yard, "2025-118").charge_moisture == pytest.approx(before)


def test_the_charge_comes_out_of_the_silo(yard: Book) -> None:
    stocked_silo(yard)
    before = holding_in(yard, "SL1").tonnes
    charge(yard)
    assert holding_in(yard, "SL1").tonnes == pytest.approx(before - 40.0)


def test_a_piece_of_the_wrong_variety_cannot_be_charged(yard: Book) -> None:
    stocked_silo(yard)
    with pytest.raises(SegregationError, match="the piece says DIAB"):
        charge_from_silo(
            yard,
            "2025-119",
            "SL1",
            "DIAB",
            2025,
            MaltStyle.PALE_ALE,
            40.0,
            "S1",
            CHARGED,
            PROGRAMME,
            SCHEDULE,
            CURVE,
        )


def test_nothing_can_be_charged_out_of_a_mixed_silo(yard: Book) -> None:
    lorry(yard, "W-1")
    lorry(yard, "W-2", purchase="P-DIAB")
    tip(yard, "SL1", "W-1", dt.date(2025, 9, 19))
    tip(yard, "SL1", "W-2", dt.date(2025, 9, 19))
    with pytest.raises(SegregationError, match="cannot declare a variety"):
        charge(yard)


def test_more_than_the_silo_holds_cannot_be_charged(yard: Book) -> None:
    stocked_silo(yard)
    with pytest.raises(StateError, match="was drawn"):
        charge(yard, tonnes=200.0)


def test_a_refused_charge_leaves_no_piece_behind(yard: Book) -> None:
    """The piece and its sources land together or not at all."""
    stocked_silo(yard)
    with pytest.raises(StateError):
        charge(yard, tonnes=200.0)
    assert yard.scalar("SELECT count(*) FROM piece") == 0


def test_a_plan_says_what_a_charge_would_carry(yard: Book) -> None:
    stocked_silo(yard)
    shares = plan_charge(yard, "SL1", 40.0, "LAUR")
    assert sum(share.tonnes for share in shares) == pytest.approx(40.0)
    assert yard.scalar("SELECT count(*) FROM piece_source") == 0


def test_a_silo_that_could_serve_a_charge_is_found(yard: Book) -> None:
    stocked_silo(yard)
    assert silo_for(yard, "LAUR", 40.0) == "SL1"


def test_no_silo_holds_enough_for_a_big_charge(yard: Book) -> None:
    stocked_silo(yard)
    assert silo_for(yard, "LAUR", 400.0) is None


def test_no_silo_holds_the_variety_asked_for(yard: Book) -> None:
    stocked_silo(yard)
    assert silo_for(yard, "DIAB", 10.0) is None


def test_an_empty_yard_can_serve_nothing(yard: Book) -> None:
    assert silo_for(yard, "LAUR", 10.0) is None


def test_the_check_says_which_thing_stops_a_charge(yard: Book) -> None:
    stocked_silo(yard)
    check_can_charge(yard, "SL1", "LAUR", 40.0)
    with pytest.raises(StateError, match="the charge wants"):
        check_can_charge(yard, "SL1", "LAUR", 400.0)


def test_the_check_refuses_an_empty_silo(yard: Book) -> None:
    with pytest.raises(StateError, match="nothing in it to charge"):
        check_can_charge(yard, "SL2", "LAUR", 10.0)
