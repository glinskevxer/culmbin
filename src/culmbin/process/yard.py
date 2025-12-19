"""Charging a piece out of a silo, which is where the traceability starts.

A piece charged with a tonnage and a moisture typed in by hand is a piece
with no history. It works, the arithmetic downstream is right, and the day
somebody rings up about a batch there is nothing to say except which steep
it was in.

Charging out of a silo fixes that in one step. The moisture comes off what
is actually in the silo, the variety is checked against what the silo holds,
and the charge is apportioned across the loads that went in, so the
`piece_source` rows are written by the act of charging rather than by
somebody remembering to.

The apportionment is proportional, because a silo is a mixed mass. Forty
tonnes out of four hundred carries a tenth of every load in there, and no
first-in-first-out story about a silo has ever been true.
"""

from __future__ import annotations

import datetime as dt

from culmbin.errors import ConflictError, StateError
from culmbin.model.enums import MaltStyle, PieceStage
from culmbin.model.process import Piece
from culmbin.model.silo import Share
from culmbin.process.floor import charge
from culmbin.store.book import Book
from culmbin.store.pieces import record_source
from culmbin.store.silos import holding_in, list_silos


def plan_charge(book: Book, silo: str, tonnes: float, variety: str) -> tuple[Share, ...]:
    """What a charge out of a silo would carry, without writing anything.

    Worth having on its own: the floor planner wants to know whether a silo
    can serve tomorrow's steep before anybody charges it.
    """
    holding = holding_in(book, silo)
    holding.check_charges(variety)
    return holding.apportion(tonnes)


def charge_from_silo(
    book: Book,
    code: str,
    silo: str,
    variety: str,
    crop_year: int,
    style: MaltStyle,
    tonnes: float,
    into: str,
    on: dt.date,
    programme: str,
    schedule: str,
    curve: str,
    share: bool = False,
) -> Piece:
    """Charge a steep out of a silo and write down where the barley came from.

    The moisture is not an argument. It is what is in the silo, because a
    typed moisture and a silo moisture that disagree is a discrepancy nobody
    can settle six weeks later.
    """
    holding = holding_in(book, silo)
    holding.check_charges(variety)
    shares = holding.apportion(tonnes)
    piece = Piece(
        code=code,
        variety=variety,
        crop_year=crop_year,
        style=style,
        charge_tonnes=tonnes,
        charge_moisture=holding.moisture,
        started=on,
        stage=PieceStage.STEEPING,
        vessel=into,
    )
    with book.writing():
        charge(book, piece, programme, schedule, curve, share=share)
        for part in shares:
            record_source(book, code, part.ticket, part.tonnes)
    return piece


def silo_for(book: Book, variety: str, tonnes: float) -> str | None:
    """The first silo that could serve a charge, in code order, or nothing.

    Deliberately the first rather than the best. There is no scoring here:
    the maltster decides which silo to draw, and this only says which ones
    are possible.
    """
    for silo in list_silos(book):
        holding = holding_in(book, silo.code)
        if holding.empty or holding.variety != variety:
            continue
        if holding.tonnes + 1e-9 >= tonnes:
            return silo.code
    return None


def check_can_charge(book: Book, silo: str, variety: str, tonnes: float) -> None:
    """Raise unless a silo could serve a charge, saying which thing stops it."""
    holding = holding_in(book, silo)
    holding.check_charges(variety)
    if holding.tonnes + 1e-9 < tonnes:
        raise StateError(f"{silo} holds {holding.tonnes:.2f}t and the charge wants {tonnes:.2f}t")
    if not holding.shares:
        raise ConflictError(f"{silo} has nothing recorded as going into it")
