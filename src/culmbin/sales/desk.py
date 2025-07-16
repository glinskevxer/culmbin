"""The sales desk: allocating a lot to a contract and getting it out of the gate.

`allocate` is the function this package exists for. Everything else here is
either a step after it or a way of looking at what it produced.

The four checks in `allocate`, and why each one is here rather than anywhere
else:

**Certified.** A lot with no analysis cannot be assessed, and shipping it is
shipping malt nobody has looked at. This is not the same as a lot that
failed: it is a lot that was never asked.

**In specification.** The lot's own analysis is assessed against the
specification the *contract* names, on the basis each clause is written on.
Two customers with different clauses about the same analyte both get the
right answer off the same analysis.

**Declares the variety.** If the contract names a variety, the lot has to be
able to say what it is, which a lot out of a mixed bin cannot. The analysis
has nothing to say about this and never had.

**Enough left.** A lot is drawn down by everything allocated against it,
including shipments that have not gone yet, because malt allocated twice is
two tankers turning up for the same forty tonnes.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from culmbin.errors import ConflictError, StateError
from culmbin.model.enums import Conformance, ShipmentState
from culmbin.model.sales import Contract, Shipment
from culmbin.model.spec import Assessment
from culmbin.store.analyses import get_analysis
from culmbin.store.bins import issue
from culmbin.store.book import Book
from culmbin.store.contracts import get_call, get_contract, list_contracts, position
from culmbin.store.lots import get_lot
from culmbin.store.shipments import (
    add_shipment,
    advance,
    get_shipment,
    list_shipments,
    reweigh,
    shipped_from_lot,
)
from culmbin.store.specs import get_specification
from culmbin.units.season import Window


@dataclass(frozen=True, slots=True)
class Availability:
    """How much of a lot is left to sell."""

    lot: str
    sealed_tonnes: float
    allocated_tonnes: float

    @property
    def free_tonnes(self) -> float:
        """What is left, never below zero."""
        return max(0.0, self.sealed_tonnes - self.allocated_tonnes)

    @property
    def empty(self) -> bool:
        """Whether there is anything left worth allocating."""
        return self.free_tonnes <= 1e-9


def availability(book: Book, lot: str) -> Availability:
    """How much of a lot has not been spoken for."""
    held = get_lot(book, lot)
    return Availability(
        lot=lot,
        sealed_tonnes=held.tonnes,
        allocated_tonnes=shipped_from_lot(book, lot),
    )


def assess_lot(book: Book, lot: str, specification: str) -> Assessment:
    """Assess a lot's own analysis against a specification.

    Refuses an uncertified lot rather than reporting every clause untested,
    because those two look identical on a report and mean very different
    things.
    """
    held = get_lot(book, lot)
    if held.analysis is None:
        raise StateError(f"{lot} has no analysis, so it cannot be assessed")
    return get_specification(book, specification).assess(get_analysis(book, held.analysis))


def allocate(
    book: Book,
    code: str,
    contract: str,
    lot: str,
    tonnes: float,
    on: dt.date,
    call: str | None = None,
    haulier: str | None = None,
    vehicle: str | None = None,
) -> Shipment:
    """Put a lot against a contract, with all four checks first."""
    held_contract = get_contract(book, contract)
    held_contract.check_open()
    if not held_contract.takes_shipment_on(on):
        raise ConflictError(f"{contract} runs {held_contract.window} and this is planned for {on}")
    if call is not None:
        called = get_call(book, call)
        if called.contract != contract:
            raise ConflictError(f"{call} is against {called.contract} and not {contract}")

    held_lot = get_lot(book, lot)
    if not held_lot.certified:
        raise StateError(f"{lot} has no analysis, so it cannot be shipped")

    assessment = assess_lot(book, lot, held_contract.specification)
    if assessment.conformance is not Conformance.PASS:
        raise ConflictError(_why_not(lot, held_contract, assessment))

    if held_contract.variety is not None:
        held_lot.check_serves(held_contract.variety)

    free = availability(book, lot)
    if tonnes > free.free_tonnes + 1e-9:
        raise ConflictError(
            f"{lot} has {free.free_tonnes:.2f}t free and {tonnes:.2f}t was allocated"
        )

    return add_shipment(
        book,
        Shipment(
            code=code,
            contract=contract,
            lot=lot,
            tonnes=tonnes,
            moisture=held_lot.moisture,
            despatched=on,
            state=ShipmentState.PLANNED,
            call=call,
            haulier=haulier,
            vehicle=vehicle,
        ),
    )


def _why_not(lot: str, contract: Contract, assessment: Assessment) -> str:
    """A sentence saying which clause stopped a lot going out."""
    if assessment.failures:
        outcome = assessment.failures[0]
        return (
            f"{lot} is {outcome.value:.2f} on {outcome.clause.label} "
            f"and {contract.specification} says {outcome.clause}"
        )
    outcome = assessment.untested[0]
    return f"{lot} has no {outcome.clause.label} result and {contract.specification} wants one"


def load(book: Book, code: str, tonnes: float, moisture: float, on: dt.date) -> Shipment:
    """Weigh a shipment off the weighbridge and take the malt out of the bin.

    The planned tonnage is a round number and the real one is not, so the
    weighbridge figure replaces it. The bin issue and the state change are
    one transaction: malt that has left the bin and is not on a shipment is
    malt nobody can find.
    """
    shipment = get_shipment(book, code)
    if shipment.state is not ShipmentState.PLANNED:
        raise StateError(f"{code} is {shipment.state} and only a planned load is weighed")
    held_lot = get_lot(book, shipment.lot)
    with book.writing():
        reweigh(book, code, tonnes, moisture)
        issue(book, held_lot.bin_code, tonnes, on, note=f"shipment {code}")
        return advance(book, code, ShipmentState.LOADED)


def despatch(book: Book, code: str) -> Shipment:
    """Send a loaded shipment out of the gate."""
    return advance(book, code, ShipmentState.DESPATCHED)


def cancel(book: Book, code: str) -> Shipment:
    """Give up a slot in the loading diary."""
    return advance(book, code, ShipmentState.CANCELLED)


def customer_book(book: Book, customer: str) -> tuple[tuple[Contract, float], ...]:
    """Every contract for a customer and what is left on it, in code order."""
    return tuple(
        (contract, position(book, contract.code).outstanding)
        for contract in list_contracts(book, customer=customer)
    )


def shipped_in(book: Book, window: Window) -> tuple[Shipment, ...]:
    """Everything that actually left over a stretch of days."""
    return list_shipments(
        book, state=ShipmentState.DESPATCHED, since=window.start, until=window.end
    )
