"""A stocked book for the intake desk tests."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.intake.standard import Standard
from culmbin.model.enums import Approval, Habit, Role
from culmbin.model.intake import Purchase
from culmbin.model.party import Party
from culmbin.model.variety import Variety
from culmbin.store.book import Book
from culmbin.store.parties import add_party
from culmbin.store.purchases import add_purchase
from culmbin.store.standards import add_standard
from culmbin.store.varieties import add_variety
from culmbin.units.season import Window

WINDOW = Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30))


@pytest.fixture
def desk(book: Book) -> Book:
    """A grower, a variety, a standard and a purchase to deliver against."""
    add_party(
        book, Party("HOLB", "Holbeach Grange", Role.GROWER, dt.date(2011, 6, 1), holding="12/345")
    )
    add_party(book, Party("WYKE", "Wykeham Farms", Role.GROWER, dt.date(2014, 3, 1)))
    add_variety(
        book, Variety("LAUR", "Laureate", Habit.SPRING, Approval.APPROVED, dt.date(2018, 12, 1))
    )
    add_variety(
        book,
        Variety(
            "PROP",
            "Propino",
            Habit.SPRING,
            Approval.WITHDRAWN,
            dt.date(2012, 12, 1),
            withdrawn=dt.date(2025, 6, 1),
        ),
    )
    add_standard(book, Standard("malting 2025"))
    add_purchase(
        book,
        Purchase(
            code="P-2025-014",
            party="HOLB",
            variety="LAUR",
            crop_year=2025,
            tonnes=480.0,
            window=WINDOW,
            standard="malting 2025",
            price_per_tonne=Decimal("232.50"),
            signed=dt.date(2025, 3, 12),
        ),
    )
    add_purchase(
        book,
        Purchase(
            code="P-2025-OLD",
            party="HOLB",
            variety="PROP",
            crop_year=2025,
            tonnes=100.0,
            window=WINDOW,
            standard="malting 2025",
            price_per_tonne=Decimal("210.00"),
            signed=dt.date(2025, 3, 12),
        ),
    )
    return book
