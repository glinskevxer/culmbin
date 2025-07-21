"""A book with a whole chain in it: lorry, piece, bin, lot, contract, shipment."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.intake.standard import Standard
from culmbin.model.enums import (
    Approval,
    Basis,
    ContractState,
    Habit,
    MaltStyle,
    Material,
    PieceStage,
    Role,
    ShipmentState,
)
from culmbin.model.intake import Delivery, Purchase
from culmbin.model.lots import Bin
from culmbin.model.party import Party
from culmbin.model.process import Piece
from culmbin.model.results import Result, analysis_of
from culmbin.model.sales import Contract, Shipment
from culmbin.model.spec import Clause, specification
from culmbin.model.variety import Variety
from culmbin.store.analyses import save_analysis
from culmbin.store.bins import add_bin, receive, seal
from culmbin.store.book import Book
from culmbin.store.contracts import add_contract
from culmbin.store.deliveries import add_delivery
from culmbin.store.lots import certify, seal_lot
from culmbin.store.parties import add_party
from culmbin.store.pieces import add_piece, record_source
from culmbin.store.purchases import add_purchase
from culmbin.store.shipments import add_shipment
from culmbin.store.specs import save_specification
from culmbin.store.standards import add_standard
from culmbin.store.varieties import add_variety
from culmbin.units.season import Window

ARRIVED = dt.date(2025, 9, 18)
BINNED = dt.date(2025, 11, 12)
SEALED = dt.date(2025, 11, 13)
GONE = dt.date(2025, 11, 20)


@pytest.fixture
def chain(book: Book) -> Book:
    """Two growers, two lorries, two pieces, one bin, one lot, one shipment."""
    add_party(
        book, Party("HOLB", "Holbeach Grange", Role.GROWER, dt.date(2011, 6, 1), holding="12/345")
    )
    add_party(
        book, Party("WYKE", "Wykeham Farms", Role.GROWER, dt.date(2011, 6, 1), holding="12/999")
    )
    add_party(book, Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, dt.date(2016, 2, 1)))
    add_variety(
        book, Variety("LAUR", "Laureate", Habit.SPRING, Approval.APPROVED, dt.date(2018, 12, 1))
    )
    add_standard(book, Standard("malting 2025"))
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
                window=Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30)),
                standard="malting 2025",
                price_per_tonne=Decimal("232.50"),
                signed=dt.date(2025, 3, 12),
            ),
        )
    for ticket, purchase, party in (
        ("W-1", "P-HOLB", "HOLB"),
        ("W-2", "P-WYKE", "WYKE"),
    ):
        add_delivery(
            book,
            Delivery(
                ticket=ticket,
                purchase=purchase,
                party=party,
                arrived=ARRIVED,
                gross_kg=43_820.0,
                tare_kg=15_640.0,
                harvested=dt.date(2025, 8, 14),
            ),
        )
    for code in ("2025-118", "2025-119"):
        add_piece(
            book,
            Piece(
                code=code,
                variety="LAUR",
                crop_year=2025,
                style=MaltStyle.LAGER,
                charge_tonnes=45.0,
                charge_moisture=12.0,
                started=dt.date(2025, 11, 3),
                stage=PieceStage.KILNED,
                vessel=None,
            ),
        )
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
            window=Window(dt.date(2025, 10, 1), dt.date(2026, 9, 30)),
            signed=dt.date(2025, 6, 2),
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
