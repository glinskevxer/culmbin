"""The traceability pages.

These are the two that get printed under pressure, so they are laid out for
somebody reading them out loud on the telephone: the names first, the
detail underneath.

The recall page opens with the customers, because that is the list somebody
is about to ring. The investigation page opens with the growers, for the
same reason from the other end.

Both say plainly when the walk is incomplete. A walk that stopped because
nobody recorded which lorry loads went into a piece looks exactly like a
walk that found nothing, and on this page those two have to be told apart.
"""

from __future__ import annotations

from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.deliveries import get_delivery
from culmbin.store.lots import get_lot
from culmbin.store.pieces import get_piece, sources_of
from culmbin.store.shipments import get_shipment, list_shipments
from culmbin.trace.walk import backward_from_shipment, forward_from_delivery


def recall_page(book: Book, ticket: str) -> str:
    """Where a lorry load of barley went, for a recall."""
    walk = forward_from_delivery(book, ticket)
    delivery = get_delivery(book, ticket)
    lot_rows = []
    for lot in walk.lots:
        held = get_lot(book, lot)
        for shipment in list_shipments(book, lot=lot):
            if shipment.state.value == "cancelled":
                continue
            lot_rows.append(
                [
                    lot,
                    held.variety or "mixed",
                    shipment.code,
                    shipment.contract,
                    f"{shipment.tonnes:.2f}",
                    shipment.despatched.isoformat(),
                    str(shipment.state),
                ]
            )
    return page(
        [
            heading(f"recall walk from {ticket}"),
            pairs(
                [
                    ("grower", delivery.party),
                    ("arrived", delivery.arrived.isoformat()),
                    ("weighed", f"{delivery.net_tonnes:.2f}"),
                    ("pieces", str(len(walk.pieces))),
                    ("lots", str(len(walk.lots))),
                ]
            ),
            ["customers to ring", *walk.customers] if walk.customers else [],
            table_block(
                "gone out",
                [
                    Column("lot"),
                    Column("variety"),
                    Column("shipment"),
                    Column("contract"),
                    Column("tonnes", Align.RIGHT),
                    Column("despatched"),
                    Column("state"),
                ],
                lot_rows,
            ),
            table_block(
                "pieces",
                [Column("piece"), Column("bins")],
                [[piece, ", ".join(walk.bins)] for piece in walk.pieces],
            ),
            ["none of this barley has left the site."] if walk.still_ours else [],
        ]
    )


def investigation_page(book: Book, shipment: str) -> str:
    """What went into a shipment, for a customer complaint."""
    walk = backward_from_shipment(book, shipment)
    load = get_shipment(book, shipment)
    rows = []
    for piece in walk.pieces:
        held = get_piece(book, piece)
        sources = sources_of(book, piece)
        rows.append(
            [
                piece,
                held.variety,
                str(held.crop_year),
                held.started.isoformat(),
                ", ".join(ticket for ticket, _ in sources) or "not recorded",
            ]
        )
    return page(
        [
            heading(f"investigation from {shipment}"),
            pairs(
                [
                    ("customer", walk.customer),
                    ("contract", load.contract),
                    ("lot", walk.lot),
                    ("tonnes", f"{load.tonnes:.2f}"),
                    ("despatched", load.despatched.isoformat()),
                ]
            ),
            ["growers behind it", *walk.growers] if walk.growers else [],
            table_block(
                "pieces in the lot",
                [
                    Column("piece"),
                    Column("variety"),
                    Column("crop"),
                    Column("started"),
                    Column("from tickets"),
                ],
                rows,
            ),
            []
            if walk.complete
            else ["this walk is incomplete: no lorry loads are recorded against these pieces."],
        ]
    )
