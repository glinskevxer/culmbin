"""The traceability walks.

A walk is a set of records at each stage rather than a tree. That is
deliberate. A lorry load goes into a silo, the silo charges several pieces,
each piece is binned with others, and a bin serves several shipments. Drawing
that as a tree gives the same piece four times over and reads as though four
pieces were involved.

What the malthouse actually needs is the *set* at each stage: which pieces,
which lots, which customers. So that is what a walk is.

Neither walk pretends to be quantitative. A load of twenty eight tonnes that
went into a silo holding four hundred is in every piece drawn off that silo
afterwards, in some proportion nobody measured. The walk answers who might
be affected, and that is the question a recall asks.
"""

from __future__ import annotations

from dataclasses import dataclass

from culmbin.errors import NotFoundError
from culmbin.store.bins import bins_holding
from culmbin.store.book import Book
from culmbin.store.deliveries import get_delivery
from culmbin.store.lots import get_lot, lots_from_piece
from culmbin.store.pieces import get_piece, pieces_from_ticket, sources_of
from culmbin.store.shipments import get_shipment, list_shipments


@dataclass(frozen=True, slots=True)
class Forward:
    """Where a lorry load of barley ended up."""

    ticket: str
    grower: str
    pieces: tuple[str, ...]
    bins: tuple[str, ...]
    lots: tuple[str, ...]
    shipments: tuple[str, ...]
    customers: tuple[str, ...]

    @property
    def reached_a_customer(self) -> bool:
        """Whether any of this barley has left the site as malt."""
        return bool(self.customers)

    @property
    def still_ours(self) -> bool:
        """Whether all of it is still on site, which is the good answer."""
        return not self.shipments


@dataclass(frozen=True, slots=True)
class Backward:
    """What went into a shipment."""

    shipment: str
    customer: str
    lot: str
    pieces: tuple[str, ...]
    tickets: tuple[str, ...]
    growers: tuple[str, ...]

    @property
    def complete(self) -> bool:
        """Whether every piece in the lot has its sources recorded.

        A walk that stops at the steep is not an answer. It looks like one,
        which is why this is a property rather than something the caller is
        expected to notice.
        """
        return bool(self.tickets)


def forward_from_delivery(book: Book, ticket: str) -> Forward:
    """Walk from a lorry load to the customers who got the malt.

    Every stage is a set. A load is in every piece drawn off the silo it went
    into, and the walk does not pretend to know in what proportion.
    """
    delivery = get_delivery(book, ticket)
    pieces = pieces_from_ticket(book, ticket)
    bins: set[str] = set()
    lots: set[str] = set()
    for piece in pieces:
        bins.update(bins_holding(book, piece))
        lots.update(lot.code for lot in lots_from_piece(book, piece))
    shipments = []
    customers: set[str] = set()
    for lot in sorted(lots):
        for shipment in list_shipments(book, lot=lot):
            if shipment.state.value == "cancelled":
                continue
            shipments.append(shipment.code)
            row = book.first("SELECT customer FROM contract WHERE code = ?", (shipment.contract,))
            if row is not None:
                customers.add(str(row["customer"]))
    return Forward(
        ticket=ticket,
        grower=delivery.party,
        pieces=pieces,
        bins=tuple(sorted(bins)),
        lots=tuple(sorted(lots)),
        shipments=tuple(sorted(shipments)),
        customers=tuple(sorted(customers)),
    )


def backward_from_shipment(book: Book, code: str) -> Backward:
    """Walk from a shipment back to the growers whose barley is in it."""
    shipment = get_shipment(book, code)
    lot = get_lot(book, shipment.lot)
    row = book.first("SELECT customer FROM contract WHERE code = ?", (shipment.contract,))
    if row is None:
        raise NotFoundError(f"{shipment.contract} is not in the book")
    tickets: set[str] = set()
    growers: set[str] = set()
    for piece in lot.parents:
        for ticket, _ in sources_of(book, piece):
            tickets.add(ticket)
            growers.add(get_delivery(book, ticket).party)
    return Backward(
        shipment=code,
        customer=str(row["customer"]),
        lot=lot.code,
        pieces=lot.parents,
        tickets=tuple(sorted(tickets)),
        growers=tuple(sorted(growers)),
    )


def customers_affected(book: Book, ticket: str) -> tuple[str, ...]:
    """Who has had malt made from a lorry load, for a recall telephone list."""
    return forward_from_delivery(book, ticket).customers


def growers_behind(book: Book, code: str) -> tuple[str, ...]:
    """Whose barley is in a shipment, for an investigation."""
    return backward_from_shipment(book, code).growers


def piece_sources_missing(book: Book, code: str) -> bool:
    """Whether a piece has no sources recorded against it.

    A piece with no sources breaks every backward walk it is part of, and it
    breaks it silently, which is why there is a way of asking.
    """
    get_piece(book, code)
    return not sources_of(book, code)
