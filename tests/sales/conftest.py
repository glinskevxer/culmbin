"""A book with a customer, a specification, a contract and a certified lot."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.model.enums import (
    Approval,
    Basis,
    ContractState,
    Habit,
    MaltStyle,
    Material,
    PieceStage,
    Role,
)
from culmbin.model.lots import Bin
from culmbin.model.party import Party
from culmbin.model.process import Piece
from culmbin.model.results import Result, analysis_of
from culmbin.model.sales import Contract
from culmbin.model.spec import Clause, specification
from culmbin.model.variety import Variety
from culmbin.store.analyses import save_analysis
from culmbin.store.bins import add_bin, receive, seal
from culmbin.store.book import Book
from culmbin.store.contracts import add_contract
from culmbin.store.lots import certify, seal_lot
from culmbin.store.parties import add_party
from culmbin.store.pieces import add_piece
from culmbin.store.specs import save_specification
from culmbin.store.varieties import add_variety
from culmbin.units.season import Window

SIGNED = dt.date(2025, 6, 2)
WINDOW = Window(dt.date(2025, 10, 1), dt.date(2026, 9, 30))
BINNED = dt.date(2025, 11, 12)
SEALED = dt.date(2025, 11, 13)


def a_piece(book: Book, code: str, variety: str) -> None:
    add_piece(
        book,
        Piece(
            code=code,
            variety=variety,
            crop_year=2025,
            style=MaltStyle.LAGER,
            charge_tonnes=45.0,
            charge_moisture=12.0,
            started=dt.date(2025, 11, 3),
            stage=PieceStage.KILNED,
            vessel=None,
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
        a_piece(book, piece, variety)
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


@pytest.fixture
def desk(book: Book) -> Book:
    """A signed lager contract and one certified Laureate lot against it."""
    add_party(book, Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, dt.date(2016, 2, 1)))
    add_variety(
        book, Variety("LAUR", "Laureate", Habit.SPRING, Approval.APPROVED, dt.date(2018, 12, 1))
    )
    add_variety(
        book, Variety("DIAB", "Diablo", Habit.SPRING, Approval.APPROVED, dt.date(2019, 12, 1))
    )
    save_specification(
        book,
        specification(
            "lager 2025",
            Material.MALT,
            [
                Clause("extract_fine", basis=Basis.DRY, minimum=80.5),
                Clause("colour", minimum=2.5, maximum=4.5),
            ],
        ),
    )
    add_contract(
        book,
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
    a_lot(book, "L-CLEAN", "B04", ("LAUR",), "M-CLEAN")
    return book
