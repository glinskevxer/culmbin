"""Whole books the tests build on.

Each function takes an empty migrated book and fills it in far enough for a
question to be asked of it. They are functions rather than fixtures so that
the fixtures can live in one conftest and be seen from every directory: a
fixture imported into a test module collides with the parameter of the same
name, which is how three directories ended up with their own copy.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from culmbin.model.enums import (
    Basis,
    ContractState,
    MaltStyle,
    Material,
    Role,
    ShipmentState,
)
from culmbin.model.intake import Delivery, Purchase
from culmbin.model.lots import Bin
from culmbin.model.party import Party
from culmbin.model.results import Result, analysis_of
from culmbin.model.sales import Contract, Shipment
from culmbin.model.spec import Clause, specification
from culmbin.store.analyses import save_analysis
from culmbin.store.bins import add_bin, receive, seal
from culmbin.store.book import Book
from culmbin.store.contracts import add_contract
from culmbin.store.deliveries import add_delivery
from culmbin.store.lots import certify, seal_lot
from culmbin.store.parties import add_party
from culmbin.store.pieces import record_source
from culmbin.store.purchases import add_purchase
from culmbin.store.shipments import add_shipment
from culmbin.store.specs import save_specification
from culmbin.units.season import Window
from tests.support.records import kilned

OPENED = dt.date(2011, 6, 1)
ARRIVED = dt.date(2025, 9, 18)
HARVESTED = dt.date(2025, 8, 14)
BINNED = dt.date(2025, 11, 12)
SEALED = dt.date(2025, 11, 13)
GONE = dt.date(2025, 11, 20)
SIGNED = dt.date(2025, 6, 2)
CONTRACT_WINDOW = Window(dt.date(2025, 10, 1), dt.date(2026, 9, 30))
BUYING_WINDOW = Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30))


def lager_specification(book: Book, name: str = "lager 2025") -> None:
    """The specification the sales tests assess against."""
    save_specification(
        book,
        specification(
            name,
            Material.MALT,
            [
                Clause("extract_fine", basis=Basis.DRY, minimum=80.5),
                Clause("colour", minimum=2.5, maximum=4.5),
            ],
        ),
    )


def a_lot(
    book: Book,
    lot: str,
    malt_bin: str,
    varieties: tuple[str, ...],
    reference: str,
    colour: float = 3.4,
    extract: float = 81.4,
    tonnes: float = 60.0,
) -> str:
    """A bin filled from one piece per variety, sealed, lotted and certified."""
    add_bin(book, Bin(malt_bin, 220.0))
    for index, variety in enumerate(varieties):
        piece = f"{lot}-P{index}"
        kilned(book, piece, variety, style=MaltStyle.LAGER)
        receive(book, malt_bin, piece, tonnes / len(varieties), 4.2, BINNED)
    seal(book, malt_bin)
    seal_lot(book, lot, malt_bin, SEALED)
    save_analysis(
        book,
        analysis_of(
            reference,
            Material.MALT,
            SEALED,
            [
                Result("malt_moisture", 4.2),
                Result("extract_fine", extract, Basis.DRY),
                Result("colour", colour),
            ],
        ),
    )
    certify(book, lot, reference)
    return lot


def sales_book(book: Book) -> Book:
    """A signed lager contract and one certified Laureate lot against it."""
    add_party(book, Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, dt.date(2016, 2, 1)))
    lager_specification(book)
    add_contract(
        book,
        Contract(
            code="C-2025-031",
            customer="BRWY",
            specification="lager 2025",
            tonnes=2400.0,
            moisture=4.5,
            price_per_tonne=Decimal("398.00"),
            window=CONTRACT_WINDOW,
            signed=SIGNED,
            state=ContractState.SIGNED,
        ),
    )
    a_lot(book, "L-CLEAN", "B04", ("LAUR",), "M-CLEAN")
    return book


def chain_book(book: Book) -> Book:
    """A whole chain: two lorries, two pieces, one bin, one lot, one shipment."""
    for code, name, holding in (
        ("HOLB", "Holbeach Grange", "12/345"),
        ("WYKE", "Wykeham Farms", "12/999"),
    ):
        add_party(book, Party(code, name, Role.GROWER, OPENED, holding=holding))
    add_party(book, Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, dt.date(2016, 2, 1)))
    save_specification(
        book,
        specification(
            "lager 2025", Material.MALT, [Clause("extract_fine", basis=Basis.DRY, minimum=80.0)]
        ),
    )
    for code, party in (("P-HOLB", "HOLB"), ("P-WYKE", "WYKE")):
        add_purchase(
            book,
            Purchase(
                code=code,
                party=party,
                variety="LAUR",
                crop_year=2025,
                tonnes=480.0,
                window=BUYING_WINDOW,
                standard="malting 2025",
                price_per_tonne=Decimal("232.50"),
                signed=dt.date(2025, 3, 12),
            ),
        )
    for ticket, purchase, party in (("W-1", "P-HOLB", "HOLB"), ("W-2", "P-WYKE", "WYKE")):
        add_delivery(
            book,
            Delivery(
                ticket=ticket,
                purchase=purchase,
                party=party,
                arrived=ARRIVED,
                gross_kg=43_820.0,
                tare_kg=15_640.0,
                harvested=HARVESTED,
            ),
        )
    for code in ("2025-118", "2025-119"):
        kilned(book, code, "LAUR", style=MaltStyle.LAGER)
        record_source(book, code, "W-1", 14.0)
        record_source(book, code, "W-2", 14.0)
    add_bin(book, Bin("B04", 220.0))
    receive(book, "B04", "2025-118", 37.9, 4.2, BINNED)
    receive(book, "B04", "2025-119", 38.1, 4.2, BINNED)
    seal(book, "B04")
    seal_lot(book, "L-1", "B04", SEALED)
    save_analysis(
        book,
        analysis_of(
            "M-1",
            Material.MALT,
            SEALED,
            [Result("malt_moisture", 4.2), Result("extract_fine", 81.4, Basis.DRY)],
        ),
    )
    certify(book, "L-1", "M-1")
    add_contract(
        book,
        Contract(
            code="C-1",
            customer="BRWY",
            specification="lager 2025",
            tonnes=2400.0,
            moisture=4.5,
            price_per_tonne=Decimal("398.00"),
            window=CONTRACT_WINDOW,
            signed=SIGNED,
            state=ContractState.SIGNED,
        ),
    )
    add_shipment(
        book,
        Shipment(
            code="S-1",
            contract="C-1",
            lot="L-1",
            tonnes=28.0,
            moisture=4.2,
            despatched=GONE,
            state=ShipmentState.DESPATCHED,
        ),
    )
    return book
