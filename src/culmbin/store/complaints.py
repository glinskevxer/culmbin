"""Reading and writing customer complaints.

A complaint is written once and then moved along. `attach` puts a shipment
on it, which is what makes it walkable back to the growers, and `close`
records what was found.

The one query worth calling out is `untraceable`. A complaint about the malt
with no shipment against it cannot be investigated at all, and a quality
meeting that counts complaints without counting those is counting the ones
that were easy to look into.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import NotFoundError
from culmbin.model.complaint import ABOUT_THE_MALT, Complaint
from culmbin.model.enums import ComplaintKind, ComplaintState
from culmbin.store.book import Book
from culmbin.store.query import narrowing, optional
from culmbin.store.rows import (
    as_date,
    as_enum,
    as_optional_date,
    as_optional_text,
    as_text,
    date_text,
    optional_date_text,
)

_COLUMNS = "code, customer, shipment, kind, state, raised, closed, summary, finding"


def _complaint(row: sqlite3.Row) -> Complaint:
    """Turn a row into a complaint."""
    return Complaint(
        code=as_text(row, "code"),
        customer=as_text(row, "customer"),
        kind=as_enum(row, "kind", ComplaintKind),
        raised=as_date(row, "raised"),
        summary=as_text(row, "summary"),
        state=as_enum(row, "state", ComplaintState),
        shipment=as_optional_text(row, "shipment"),
        closed=as_optional_date(row, "closed"),
        finding=as_text(row, "finding"),
    )


def _write(book: Book, complaint: Complaint) -> Complaint:
    """Write a complaint that is already there."""
    book.execute(
        "UPDATE complaint SET shipment = ?, state = ?, closed = ?, finding = ? WHERE code = ?",
        (
            complaint.shipment,
            complaint.state,
            optional_date_text(complaint.closed),
            complaint.finding,
            complaint.code,
        ),
    )
    return complaint


def raise_complaint(book: Book, complaint: Complaint) -> Complaint:
    """Write down a telephone call."""
    book.execute(
        f"INSERT INTO complaint ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            complaint.code,
            complaint.customer,
            complaint.shipment,
            complaint.kind,
            complaint.state,
            date_text(complaint.raised),
            optional_date_text(complaint.closed),
            complaint.summary,
            complaint.finding,
        ),
    )
    return complaint


def get_complaint(book: Book, code: str) -> Complaint:
    """One complaint, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM complaint WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no complaint called {code!r}")
    return _complaint(row)


def find_complaint(book: Book, code: str) -> Complaint | None:
    """One complaint, or nothing."""
    return optional(lambda: get_complaint(book, code))


def attach(book: Book, code: str, shipment: str) -> Complaint:
    """Put a shipment on a complaint, which is what makes it walkable back."""
    return _write(book, get_complaint(book, code).attached_to(shipment))


def investigate(book: Book, code: str) -> Complaint:
    """Move a complaint from open to being looked into."""
    complaint = get_complaint(book, code)
    return _write(
        book,
        Complaint(
            code=complaint.code,
            customer=complaint.customer,
            kind=complaint.kind,
            raised=complaint.raised,
            summary=complaint.summary,
            state=ComplaintState.INVESTIGATING,
            shipment=complaint.shipment,
        ),
    )


def close(book: Book, code: str, state: ComplaintState, on: dt.date, finding: str) -> Complaint:
    """Close a complaint, with what was found written down."""
    return _write(book, get_complaint(book, code).closed_as(state, on, finding))


def list_complaints(
    book: Book,
    customer: str | None = None,
    state: ComplaintState | None = None,
    kind: ComplaintKind | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> tuple[Complaint, ...]:
    """Every complaint, oldest first, narrowed the five ways the desk asks."""
    narrow = narrowing().maybe("customer = ?", customer).maybe("state = ?", state)
    narrow.maybe("kind = ?", kind).since("raised", since).until("raised", until)
    rows = book.query(
        f"SELECT {_COLUMNS} FROM complaint{narrow.where} ORDER BY raised, code", narrow.values
    )
    return tuple(_complaint(row) for row in rows)


def open_complaints(book: Book) -> tuple[Complaint, ...]:
    """Everything still waiting on somebody, oldest first."""
    narrow = narrowing().one_of("state", [ComplaintState.OPEN, ComplaintState.INVESTIGATING])
    rows = book.query(
        f"SELECT {_COLUMNS} FROM complaint{narrow.where} ORDER BY raised, code", narrow.values
    )
    return tuple(_complaint(row) for row in rows)


def untraceable(book: Book) -> tuple[Complaint, ...]:
    """Every complaint about the malt with no shipment against it.

    A quality meeting that counts complaints without counting these is
    counting the ones that happened to be easy to look into.
    """
    narrow = narrowing().always("shipment IS NULL")
    narrow.one_of("kind", sorted(ABOUT_THE_MALT))
    rows = book.query(
        f"SELECT {_COLUMNS} FROM complaint{narrow.where} ORDER BY raised, code", narrow.values
    )
    return tuple(_complaint(row) for row in rows)


def count_by_kind(book: Book, since: dt.date | None = None) -> dict[ComplaintKind, int]:
    """How many complaints there were of each kind, zeroes included.

    The zeroes are the point. A kind with none is a fact about the season
    and a kind missing from the table is a question nobody asked.
    """
    counts: dict[ComplaintKind, int] = dict.fromkeys(ComplaintKind, 0)
    for complaint in list_complaints(book, since=since):
        counts[complaint.kind] += 1
    return counts
