"""Reading and writing deliveries.

A delivery is written when the lorry tips and is not changed afterwards,
with one exception: the sample reference goes on later, because the sample
goes to the lab after the barley is already in the pit.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.intake import Delivery
from culmbin.store.book import Book
from culmbin.store.query import narrowing, optional
from culmbin.store.rows import (
    as_date,
    as_number,
    as_optional_date,
    as_optional_text,
    as_text,
    date_text,
    optional_date_text,
)

_COLUMNS = (
    "ticket, purchase, party, arrived, gross_kg, tare_kg, haulier, vehicle, sample, harvested"
)


def _delivery(row: sqlite3.Row) -> Delivery:
    """Turn a row into a delivery."""
    return Delivery(
        ticket=as_text(row, "ticket"),
        purchase=as_text(row, "purchase"),
        party=as_text(row, "party"),
        arrived=as_date(row, "arrived"),
        gross_kg=as_number(row, "gross_kg"),
        tare_kg=as_number(row, "tare_kg"),
        haulier=as_optional_text(row, "haulier"),
        vehicle=as_optional_text(row, "vehicle"),
        sample=as_optional_text(row, "sample"),
        harvested=as_optional_date(row, "harvested"),
    )


def add_delivery(book: Book, delivery: Delivery) -> Delivery:
    """Write a new delivery."""
    book.execute(
        f"INSERT INTO delivery ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            delivery.ticket,
            delivery.purchase,
            delivery.party,
            date_text(delivery.arrived),
            delivery.gross_kg,
            delivery.tare_kg,
            delivery.haulier,
            delivery.vehicle,
            delivery.sample,
            optional_date_text(delivery.harvested),
        ),
    )
    return delivery


def get_delivery(book: Book, ticket: str) -> Delivery:
    """One delivery, or say which ticket was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM delivery WHERE ticket = ?", (ticket,))
    if row is None:
        raise NotFoundError(f"no delivery on ticket {ticket!r}")
    return _delivery(row)


def find_delivery(book: Book, ticket: str) -> Delivery | None:
    """One delivery, or nothing."""
    return optional(lambda: get_delivery(book, ticket))


def attach_sample(book: Book, ticket: str, reference: str) -> Delivery:
    """Put a sample reference on a delivery that has not got one.

    Refuses to move a sample. Two samples off one lorry means the second one
    is a retest, and a retest belongs to the load through its own analysis
    reference rather than by replacing the first.
    """
    delivery = get_delivery(book, ticket)
    if delivery.sampled:
        raise ConflictError(f"ticket {ticket} was already sampled as {delivery.sample}")
    book.execute("UPDATE delivery SET sample = ? WHERE ticket = ?", (reference, ticket))
    return get_delivery(book, ticket)


def record_harvest(book: Book, ticket: str, harvested: dt.date) -> Delivery:
    """Put a harvest date on a delivery, which is what the grower's paperwork gives.

    Without it a load cannot be graded, because whether it is new crop
    decides which rejections apply. Refuses to move one that is there, for
    the same reason a sample cannot be moved.
    """
    delivery = get_delivery(book, ticket)
    if delivery.dated:
        raise ConflictError(f"ticket {ticket} is already cut on {delivery.harvested}")
    if harvested > delivery.arrived:
        raise ConflictError(f"ticket {ticket} arrived on {delivery.arrived}, before {harvested}")
    book.execute(
        "UPDATE delivery SET harvested = ? WHERE ticket = ?", (date_text(harvested), ticket)
    )
    return get_delivery(book, ticket)


def undated(book: Book) -> tuple[Delivery, ...]:
    """Every delivery with no harvest date on it yet, oldest first."""
    rows = book.query(
        f"SELECT {_COLUMNS} FROM delivery WHERE harvested IS NULL ORDER BY arrived, ticket"
    )
    return tuple(_delivery(row) for row in rows)


def list_deliveries(
    book: Book,
    purchase: str | None = None,
    party: str | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> tuple[Delivery, ...]:
    """Every delivery, oldest first, narrowed the four ways the office asks."""
    narrow = narrowing().maybe("purchase = ?", purchase).maybe("party = ?", party)
    narrow.since("arrived", since).until("arrived", until)
    rows = book.query(
        f"SELECT {_COLUMNS} FROM delivery{narrow.where} ORDER BY arrived, ticket", narrow.values
    )
    return tuple(_delivery(row) for row in rows)


def unsampled(book: Book, until: dt.date | None = None) -> tuple[Delivery, ...]:
    """Every delivery still waiting on a sample, oldest first.

    This is the list the intake office works off in the morning. A load that
    is in the pit and has not been graded is barley we have taken in and
    cannot pay for.
    """
    narrow = narrowing().always("sample IS NULL").until("arrived", until)
    rows = book.query(
        f"SELECT {_COLUMNS} FROM delivery{narrow.where} ORDER BY arrived, ticket", narrow.values
    )
    return tuple(_delivery(row) for row in rows)
