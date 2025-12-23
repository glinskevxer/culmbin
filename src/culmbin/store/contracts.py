"""Reading and writing contracts and call-offs, and where a contract stands.

The position is worked, never stored. It is the sum of the contract tonnes
of every shipment that counts, and the contract tonne of a shipment depends
on the shipment's own moisture and the contract's, so a stored figure would
have to be recomputed every time either of them was corrected.

A shipment counts once it is loaded. A planned one is a slot in the loading
diary and the malt is still in the bin, so it is on the *committed* figure
and not on the delivered one. Those two are different numbers and the sales
desk asks for both.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import ContractState
from culmbin.model.sales import Call, Contract
from culmbin.store.book import Book
from culmbin.store.query import narrowing, optional
from culmbin.store.rows import (
    as_date,
    as_enum,
    as_money,
    as_number,
    as_optional_text,
    as_text,
    date_text,
    money_text,
)
from culmbin.units.mass import at_moisture
from culmbin.units.season import Window

_COLUMNS = (
    "code, customer, specification, tonnes, moisture, price_per_tonne, "
    "window_start, window_end, signed, state, variety"
)

_CALL_COLUMNS = "code, contract, tonnes, week_start, week_end, placed"


@dataclass(frozen=True, slots=True)
class Position:
    """Where a contract stands today."""

    contract: str
    contracted: float
    delivered: float
    committed: float

    @property
    def outstanding(self) -> float:
        """Contract tonnes still to ship, counting what is loaded and gone.

        Never below zero. An over shipped contract has nothing left, and the
        sales desk would rather be told that than minus four tonnes.
        """
        return max(0.0, self.contracted - self.delivered)

    @property
    def uncommitted(self) -> float:
        """Contract tonnes with nothing at all against them yet."""
        return max(0.0, self.contracted - self.committed)

    @property
    def complete(self) -> bool:
        """Whether the contract has been served in full."""
        return self.outstanding <= 1e-9

    @property
    def percent_delivered(self) -> float:
        """How far through the contract is, as a percentage."""
        if self.contracted <= 0.0:
            return 0.0
        return self.delivered / self.contracted * 100.0


def _contract(row: sqlite3.Row) -> Contract:
    """Turn a row into a contract."""
    return Contract(
        code=as_text(row, "code"),
        customer=as_text(row, "customer"),
        specification=as_text(row, "specification"),
        tonnes=as_number(row, "tonnes"),
        moisture=as_number(row, "moisture"),
        price_per_tonne=as_money(row, "price_per_tonne"),
        window=Window(as_date(row, "window_start"), as_date(row, "window_end")),
        signed=as_date(row, "signed"),
        state=as_enum(row, "state", ContractState),
        variety=as_optional_text(row, "variety"),
    )


def _call(row: sqlite3.Row) -> Call:
    """Turn a row into a call-off."""
    return Call(
        code=as_text(row, "code"),
        contract=as_text(row, "contract"),
        tonnes=as_number(row, "tonnes"),
        wanted=Window(as_date(row, "week_start"), as_date(row, "week_end")),
        placed=as_date(row, "placed"),
    )


def add_contract(book: Book, contract: Contract) -> Contract:
    """Write a new contract."""
    book.execute(
        f"INSERT INTO contract ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            contract.code,
            contract.customer,
            contract.specification,
            contract.tonnes,
            contract.moisture,
            money_text(contract.price_per_tonne),
            date_text(contract.window.start),
            date_text(contract.window.end),
            date_text(contract.signed),
            contract.state,
            contract.variety,
        ),
    )
    return contract


def get_contract(book: Book, code: str) -> Contract:
    """One contract, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM contract WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no contract called {code!r}")
    return _contract(row)


def find_contract(book: Book, code: str) -> Contract | None:
    """One contract, or nothing."""
    return optional(lambda: get_contract(book, code))


def set_state(book: Book, code: str, state: ContractState) -> Contract:
    """Move a contract along.

    A cancelled or closed contract does not come back. Reopening one would
    let malt ship against a contract the customer thinks is finished, and
    the fix for a contract closed too early is a new one.
    """
    contract = get_contract(book, code)
    if contract.state in (ContractState.CLOSED, ContractState.CANCELLED):
        raise StateError(f"{code} is {contract.state} and does not reopen")
    if state is contract.state:
        raise ConflictError(f"{code} is already {state}")
    book.execute("UPDATE contract SET state = ? WHERE code = ?", (state, code))
    return get_contract(book, code)


def list_contracts(
    book: Book, customer: str | None = None, state: ContractState | None = None
) -> tuple[Contract, ...]:
    """Every contract, in code order, narrowed by customer and by state."""
    narrow = narrowing().maybe("customer = ?", customer).maybe("state = ?", state)
    rows = book.query(f"SELECT {_COLUMNS} FROM contract{narrow.where} ORDER BY code", narrow.values)
    return tuple(_contract(row) for row in rows)


def add_call(book: Book, call: Call) -> Call:
    """Write a call-off against a contract.

    Refuses a call that would take the contract past its tonnage, because
    that is a conversation with the customer rather than a keystroke.
    """
    contract = get_contract(book, call.contract)
    contract.check_open()
    if not contract.window.overlaps(call.wanted):
        raise ConflictError(
            f"{call.code} wants {call.wanted} and {contract.code} runs {contract.window}"
        )
    already = called_tonnes(book, contract.code)
    if already + call.tonnes > contract.tonnes + 1e-9:
        raise ConflictError(
            f"{call.code} would take {contract.code} to "
            f"{already + call.tonnes:.1f}t against {contract.tonnes:.1f}t"
        )
    book.execute(
        f"INSERT INTO call_off ({_CALL_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
        (
            call.code,
            call.contract,
            call.tonnes,
            date_text(call.wanted.start),
            date_text(call.wanted.end),
            date_text(call.placed),
        ),
    )
    return call


def get_call(book: Book, code: str) -> Call:
    """One call-off, or say which one was asked for."""
    row = book.first(f"SELECT {_CALL_COLUMNS} FROM call_off WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no call called {code!r}")
    return _call(row)


def list_calls(
    book: Book, contract: str | None = None, window: Window | None = None
) -> tuple[Call, ...]:
    """Every call-off, in date order, narrowed by contract and by week."""
    narrow = narrowing().maybe("contract = ?", contract)
    if window is not None:
        narrow.until("week_start", window.end).since("week_end", window.start)
    rows = book.query(
        f"SELECT {_CALL_COLUMNS} FROM call_off{narrow.where} ORDER BY week_start, code",
        narrow.values,
    )
    return tuple(_call(row) for row in rows)


def called_tonnes(book: Book, contract: str) -> float:
    """Everything the customer has asked for against a contract."""
    total = book.scalar("SELECT total(tonnes) FROM call_off WHERE contract = ?", (contract,))
    return float(total or 0.0)


def position(book: Book, code: str) -> Position:
    """Where a contract stands, worked off the shipments.

    Delivered is what has gone. Committed is that plus what is planned, and
    the two differ by whatever is sitting in the loading diary.
    """
    contract = get_contract(book, code)
    rows = book.query("SELECT tonnes, moisture, state FROM shipment WHERE contract = ?", (code,))
    delivered = 0.0
    committed = 0.0
    for row in rows:
        state = as_text(row, "state")
        if state == "cancelled":
            continue
        tonnes = at_moisture(
            as_number(row, "tonnes"), as_number(row, "moisture"), contract.moisture
        )
        committed += tonnes
        if state in ("loaded", "despatched"):
            delivered += tonnes
    return Position(
        contract=code,
        contracted=contract.tonnes,
        delivered=delivered,
        committed=committed,
    )


def open_contracts_on(book: Book, day: dt.date) -> tuple[Contract, ...]:
    """Every signed contract whose window covers a day, in code order."""
    return tuple(
        contract
        for contract in list_contracts(book, state=ContractState.SIGNED)
        if contract.takes_shipment_on(day)
    )
