"""A book with a week of intake in it."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.intake.desk import grade_load, take_sample, weigh_in
from culmbin.intake.standard import Standard
from culmbin.model.enums import Approval, Habit, RejectionReason, Role
from culmbin.model.intake import Delivery, Purchase
from culmbin.model.party import Party
from culmbin.model.results import Analysis
from culmbin.model.variety import Variety
from culmbin.store.book import Book
from culmbin.store.parties import add_party
from culmbin.store.purchases import add_purchase
from culmbin.store.standards import add_standard
from culmbin.store.varieties import add_variety
from culmbin.units.season import Window
from tests.support.samples import barley_sample

ARRIVED = dt.date(2025, 9, 18)
HARVESTED = dt.date(2025, 8, 14)
GRADED = dt.date(2025, 9, 19)
WEEK = Window(dt.date(2025, 9, 15), dt.date(2025, 9, 21))


def sample(reference: str, **overrides: float) -> Analysis:
    return barley_sample(reference, ARRIVED, **overrides)


def lorry(book: Book, ticket: str, party: str = "HOLB", **overrides: float) -> None:
    """A lorry tipped, sampled and graded."""
    weigh_in(
        book,
        Delivery(
            ticket=ticket,
            purchase=f"P-{party}",
            party=party,
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
            harvested=HARVESTED,
        ),
    )
    take_sample(book, ticket, sample(f"B-{ticket}", **overrides))
    grade_load(book, ticket, GRADED)


@pytest.fixture
def week(book: Book) -> Book:
    """Two growers with a purchase each and nothing delivered yet."""
    for code, name in (("HOLB", "Holbeach Grange"), ("WYKE", "Wykeham Farms")):
        add_party(book, Party(code, name, Role.GROWER, dt.date(2011, 6, 1), holding="12/345"))
        add_purchase(
            book,
            Purchase(
                code=f"P-{code}",
                party=code,
                variety="LAUR",
                crop_year=2025,
                tonnes=480.0,
                window=Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30)),
                standard="malting 2025",
                price_per_tonne=Decimal("232.50"),
                signed=dt.date(2025, 3, 12),
            ),
        )
    return book


@pytest.fixture(autouse=True)
def _registers(book: Book) -> None:
    add_variety(
        book, Variety("LAUR", "Laureate", Habit.SPRING, Approval.APPROVED, dt.date(2018, 12, 1))
    )
    add_standard(book, Standard("malting 2025"))


REJECTED = RejectionReason.GERMINATION
