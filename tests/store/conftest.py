"""Fixtures for the store tests.

Nearly every table in the book refers to a register, so a test that writes a
delivery needs a grower, a variety, a standard and a purchase before it can
write anything at all. `stocked` is that, once.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.intake.standard import Standard
from culmbin.model.enums import Approval, Habit, Role, VesselKind
from culmbin.model.intake import Purchase
from culmbin.model.party import Party
from culmbin.model.plant import Vessel
from culmbin.model.variety import Variety
from culmbin.store.book import Book
from culmbin.store.parties import add_party
from culmbin.store.purchases import add_purchase
from culmbin.store.standards import add_standard
from culmbin.store.varieties import add_variety
from culmbin.store.vessels import add_vessel
from culmbin.units.season import Window

WINDOW = Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30))


@pytest.fixture
def stocked(book: Book) -> Book:
    """A book with the registers a delivery needs already in it."""
    opened = dt.date(2011, 6, 1)
    listed = dt.date(2018, 12, 1)
    add_party(book, Party("HOLB", "Holbeach Grange", Role.GROWER, opened, holding="12/345"))
    add_party(book, Party("WYKE", "Wykeham Farms", Role.GROWER, opened, holding="12/999"))
    add_party(book, Party("HAUL", "Ketton Haulage", Role.HAULIER, opened))
    add_party(book, Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, opened))
    add_variety(book, Variety("LAUR", "Laureate", Habit.SPRING, Approval.APPROVED, listed))
    add_variety(book, Variety("DIAB", "Diablo", Habit.SPRING, Approval.APPROVED, listed))
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
    add_vessel(
        book,
        Vessel("S1", "steep 1", VesselKind.STEEP, dt.date(1998, 4, 1), charge_limit_t=45.0),
    )
    add_vessel(
        book,
        Vessel(
            "G1",
            "box 1",
            VesselKind.BOX,
            dt.date(1998, 4, 1),
            floor_area_m2=120.0,
            depth_limit_cm=90.0,
        ),
    )
    return book
