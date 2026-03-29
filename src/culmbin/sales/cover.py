"""What can be promised: contracts against malt, and malt against contracts.

The sales desk asks this in two directions and they are different questions.

**Can I sign another two hundred tonnes of lager?** That is contracts
against malt, and the answer is what is uncommitted on the contracts already
signed set beside what is in the bins and on the floor.

**What am I going to do with bin four?** That is malt against contracts, and
the answer is which signed contracts a lot could actually serve, which is
the four checks in `culmbin.sales.desk` asked in advance instead of at the
loading bay.

Neither answer is a promise. Malt on the floor is four days from being malt
and might come off out of specification, so it is counted separately from
malt in a bin and never added to it.
"""

from __future__ import annotations

from dataclasses import dataclass

from culmbin.errors import StateError
from culmbin.model.enums import Conformance, ContractState, PieceStage
from culmbin.model.sales import Contract
from culmbin.process.losses import TYPICAL_MALTING_LOSS, expected_malt_tonnes
from culmbin.sales.desk import assess_lot, availability
from culmbin.store.book import Book
from culmbin.store.contracts import get_contract, list_contracts, position
from culmbin.store.lots import get_lot, list_lots
from culmbin.store.pieces import list_pieces

IN_PROCESS = (PieceStage.STEEPING, PieceStage.GERMINATING, PieceStage.KILNING)


@dataclass(frozen=True, slots=True)
class Cover:
    """Malt against contracts, at one moment."""

    sealed_tonnes: float
    free_tonnes: float
    coming_tonnes: float
    outstanding_tonnes: float
    uncommitted_tonnes: float

    @property
    def short_by(self) -> float:
        """Contract tonnes with no malt behind them, counting only what is in a bin.

        Never below zero. A desk that is covered is covered, and telling it
        that it is minus four hundred tonnes short reads as a mistake.
        """
        return max(0.0, self.outstanding_tonnes - self.free_tonnes)

    @property
    def short_by_with_the_floor(self) -> float:
        """The same figure counting what is on the floor as well.

        Worth having and worth keeping separate. Malt on the floor is four
        days off and might come off out of specification.
        """
        return max(0.0, self.outstanding_tonnes - self.free_tonnes - self.coming_tonnes)

    @property
    def covered(self) -> bool:
        """Whether everything signed could be served out of the bins today."""
        return self.short_by <= 1e-9


def cover(book: Book) -> Cover:
    """Where the whole book stands: malt in hand against malt promised."""
    sealed = 0.0
    free = 0.0
    for lot in list_lots(book):
        sealed += lot.tonnes
        free += availability(book, lot.code).free_tonnes
    coming = sum(
        expected_malt_tonnes(piece.charge_tonnes, piece.charge_moisture, 4.5, TYPICAL_MALTING_LOSS)
        for piece in list_pieces(book)
        if piece.stage in IN_PROCESS
    )
    outstanding = 0.0
    uncommitted = 0.0
    for contract in list_contracts(book, state=ContractState.SIGNED):
        where = position(book, contract.code)
        outstanding += where.outstanding
        uncommitted += where.uncommitted
    return Cover(
        sealed_tonnes=sealed,
        free_tonnes=free,
        coming_tonnes=coming,
        outstanding_tonnes=outstanding,
        uncommitted_tonnes=uncommitted,
    )


def contracts_a_lot_could_serve(book: Book, lot: str) -> tuple[Contract, ...]:
    """Every signed contract a lot could actually go against, in code order.

    The four checks from the loading bay, asked in advance. A lot that meets
    nothing is worth knowing about before it has been sitting in a bin for
    three months.
    """
    held = get_lot(book, lot)
    if not held.certified:
        raise StateError(f"{lot} has no analysis, so nothing can be said about it")
    out = []
    for contract in list_contracts(book, state=ContractState.SIGNED):
        if contract.variety is not None and not held.serves(contract.variety):
            continue
        assessment = assess_lot(book, lot, contract.specification)
        if assessment.conformance is Conformance.PASS:
            out.append(contract)
    return tuple(out)


def lots_a_contract_could_take(book: Book, contract: str) -> tuple[str, ...]:
    """Every certified lot with malt left that could serve a contract."""
    held = get_contract(book, contract)
    out = []
    for lot in list_lots(book, certified=True):
        if held.variety is not None and not lot.serves(held.variety):
            continue
        if availability(book, lot.code).empty:
            continue
        if assess_lot(book, lot.code, held.specification).conformance is Conformance.PASS:
            out.append(lot.code)
    return tuple(out)


def orphan_lots(book: Book) -> tuple[str, ...]:
    """Every certified lot with malt left that no signed contract can take.

    This is the list worth reading. A lot that meets nothing is stock in
    name only, and the longer nobody notices the fewer options there are.
    """
    return tuple(
        lot.code
        for lot in list_lots(book, certified=True)
        if not availability(book, lot.code).empty
        and not contracts_a_lot_could_serve(book, lot.code)
    )
