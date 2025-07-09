"""Reading and writing shipments.

A shipment moves through four states and only forwards. Planned is a slot in
the loading diary, loaded is malt on a lorry in the yard, despatched is the
lorry gone, and cancelled is the slot given up.

Cancelling a despatched shipment is refused. The lorry has gone; whatever
went wrong is a credit note and a return, both of which are somebody else's
records, and unpicking the despatch here would take the malt off the
customer's contract position as though it had never been sent.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import ShipmentState
from culmbin.model.sales import Shipment
from culmbin.store.book import Book
from culmbin.store.rows import (
    as_date,
    as_enum,
    as_number,
    as_optional_text,
    as_text,
    date_text,
)

_COLUMNS = "code, contract, lot, tonnes, moisture, despatched, state, call_off, haulier, vehicle"

_NEXT: dict[ShipmentState, frozenset[ShipmentState]] = {
    ShipmentState.PLANNED: frozenset({ShipmentState.LOADED, ShipmentState.CANCELLED}),
    ShipmentState.LOADED: frozenset({ShipmentState.DESPATCHED, ShipmentState.CANCELLED}),
    ShipmentState.DESPATCHED: frozenset(),
    ShipmentState.CANCELLED: frozenset(),
}
"""What each state can become.

Despatched and cancelled are both ends. A lorry that has gone has gone, and
a slot that was given up is given up: the second one is written again as a
new shipment rather than resurrected, so that the loading diary shows what
actually happened.
"""


def _shipment(row: sqlite3.Row) -> Shipment:
    """Turn a row into a shipment."""
    return Shipment(
        code=as_text(row, "code"),
        contract=as_text(row, "contract"),
        lot=as_text(row, "lot"),
        tonnes=as_number(row, "tonnes"),
        moisture=as_number(row, "moisture"),
        despatched=as_date(row, "despatched"),
        state=as_enum(row, "state", ShipmentState),
        call=as_optional_text(row, "call_off"),
        haulier=as_optional_text(row, "haulier"),
        vehicle=as_optional_text(row, "vehicle"),
    )


def add_shipment(book: Book, shipment: Shipment) -> Shipment:
    """Write a new shipment."""
    book.execute(
        f"INSERT INTO shipment ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            shipment.code,
            shipment.contract,
            shipment.lot,
            shipment.tonnes,
            shipment.moisture,
            date_text(shipment.despatched),
            shipment.state,
            shipment.call,
            shipment.haulier,
            shipment.vehicle,
        ),
    )
    return shipment


def get_shipment(book: Book, code: str) -> Shipment:
    """One shipment, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM shipment WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no shipment called {code!r}")
    return _shipment(row)


def find_shipment(book: Book, code: str) -> Shipment | None:
    """One shipment, or nothing."""
    try:
        return get_shipment(book, code)
    except NotFoundError:
        return None


def advance(book: Book, code: str, state: ShipmentState) -> Shipment:
    """Move a shipment to its next state, or say why it will not go."""
    shipment = get_shipment(book, code)
    allowed = _NEXT[shipment.state]
    if not allowed:
        raise StateError(f"{code} is {shipment.state} and does not change again")
    if state not in allowed:
        raise StateError(f"{code} is {shipment.state} and cannot go to {state}")
    book.execute("UPDATE shipment SET state = ? WHERE code = ?", (state, code))
    return get_shipment(book, code)


def reweigh(book: Book, code: str, tonnes: float, moisture: float) -> Shipment:
    """Correct the weight and moisture of a shipment that has not gone.

    The weighbridge ticket comes off the lorry after it is loaded, so a
    planned tonnage is nearly always a round number and the real one is not.
    A despatched shipment is not corrected here: it has been invoiced.
    """
    shipment = get_shipment(book, code)
    if shipment.state in (ShipmentState.DESPATCHED, ShipmentState.CANCELLED):
        raise StateError(f"{code} is {shipment.state} and is not reweighed")
    if tonnes <= 0.0:
        raise ConflictError(f"a shipment of {tonnes} tonnes is not a shipment")
    book.execute(
        "UPDATE shipment SET tonnes = ?, moisture = ? WHERE code = ?", (tonnes, moisture, code)
    )
    return get_shipment(book, code)


def list_shipments(
    book: Book,
    contract: str | None = None,
    lot: str | None = None,
    state: ShipmentState | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> tuple[Shipment, ...]:
    """Every shipment, oldest first, narrowed the five ways the desk asks."""
    clauses = []
    params: list[object] = []
    if contract is not None:
        clauses.append("contract = ?")
        params.append(contract)
    if lot is not None:
        clauses.append("lot = ?")
        params.append(lot)
    if state is not None:
        clauses.append("state = ?")
        params.append(state)
    if since is not None:
        clauses.append("despatched >= ?")
        params.append(date_text(since))
    if until is not None:
        clauses.append("despatched <= ?")
        params.append(date_text(until))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.query(f"SELECT {_COLUMNS} FROM shipment{where} ORDER BY despatched, code", params)
    return tuple(_shipment(row) for row in rows)


def shipped_from_lot(book: Book, lot: str) -> float:
    """How much has gone out of a lot, counting what is planned.

    Planned counts here even though it does not count against a contract,
    because the malt is spoken for and allocating it twice is how two
    tankers turn up for the same forty tonnes.
    """
    total = book.scalar(
        "SELECT total(tonnes) FROM shipment WHERE lot = ? AND state != 'cancelled'", (lot,)
    )
    return float(total or 0.0)


def loading_diary(book: Book, window_start: dt.date, window_end: dt.date) -> tuple[Shipment, ...]:
    """Everything planned or loaded over a stretch of days.

    This is the yard's list. What has gone is on the contract position and
    is nobody's problem any more.
    """
    rows = book.query(
        f"SELECT {_COLUMNS} FROM shipment "
        "WHERE state IN ('planned', 'loaded') AND despatched >= ? AND despatched <= ? "
        "ORDER BY despatched, code",
        (date_text(window_start), date_text(window_end)),
    )
    return tuple(_shipment(row) for row in rows)
