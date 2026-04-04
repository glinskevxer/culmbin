"""The sales pages: where the contracts stand and what is going out.

`contract_page` is the month end question. It carries three tonnages, and
they are three different things: what was signed, what has actually gone,
and what is committed including the loads in the diary that have not moved.
Reporting only the middle one is how a sales desk discovers in August that
it has sold the same four hundred tonnes twice.

`diary_page` is the yard's list for the week.
"""

from __future__ import annotations

import datetime as dt

from culmbin.model.enums import ContractState
from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.sales.cover import contracts_a_lot_could_serve, cover, orphan_lots
from culmbin.sales.desk import availability
from culmbin.store.book import Book
from culmbin.store.contracts import called_tonnes, list_contracts, position
from culmbin.store.lots import list_lots
from culmbin.store.shipments import loading_diary
from culmbin.units.season import Window


def contract_page(book: Book, customer: str | None = None) -> str:
    """Every signed contract and where it stands."""
    rows = []
    signed = 0.0
    delivered = 0.0
    for contract in list_contracts(book, customer=customer, state=ContractState.SIGNED):
        where = position(book, contract.code)
        signed += contract.tonnes
        delivered += where.delivered
        rows.append(
            [
                contract.code,
                contract.customer,
                contract.specification,
                contract.variety or "",
                f"{contract.tonnes:.0f}",
                f"{where.delivered:.1f}",
                f"{where.committed:.1f}",
                f"{where.outstanding:.1f}",
                f"{where.percent_delivered:.0f}%",
            ]
        )
    title = "contract position" if customer is None else f"{customer} contract position"
    return page(
        [
            heading(title),
            pairs(
                [
                    ("contracts", str(len(rows))),
                    ("signed tonnes", f"{signed:.0f}"),
                    ("delivered tonnes", f"{delivered:.1f}"),
                ]
            ),
            table_block(
                "signed contracts",
                [
                    Column("contract"),
                    Column("customer"),
                    Column("specification"),
                    Column("variety"),
                    Column("signed", Align.RIGHT),
                    Column("gone", Align.RIGHT),
                    Column("committed", Align.RIGHT),
                    Column("left", Align.RIGHT),
                    Column("done", Align.RIGHT),
                ],
                rows,
            ),
            [] if rows else ["there are no signed contracts."],
        ]
    )


def call_page(book: Book, window: Window) -> str:
    """What customers have asked for against each contract."""
    rows = []
    for contract in list_contracts(book, state=ContractState.SIGNED):
        called = called_tonnes(book, contract.code)
        if called <= 0.0:
            continue
        rows.append(
            [
                contract.code,
                contract.customer,
                f"{contract.tonnes:.0f}",
                f"{called:.0f}",
                f"{max(0.0, contract.tonnes - called):.0f}",
            ]
        )
    return page(
        [
            heading(f"call-offs {window}"),
            table_block(
                "against contract",
                [
                    Column("contract"),
                    Column("customer"),
                    Column("signed", Align.RIGHT),
                    Column("called", Align.RIGHT),
                    Column("uncalled", Align.RIGHT),
                ],
                rows,
            ),
            [] if rows else ["nothing has been called off."],
        ]
    )


def diary_page(book: Book, start: dt.date, end: dt.date) -> str:
    """Everything planned or loaded over a stretch of days.

    What has gone is on the contract position and is nobody's problem here.
    """
    rows = [
        [
            shipment.code,
            shipment.despatched.isoformat(),
            shipment.contract,
            shipment.lot,
            f"{shipment.tonnes:.2f}",
            str(shipment.state),
            shipment.vehicle or "",
        ]
        for shipment in loading_diary(book, start, end)
    ]
    tonnes = sum(float(row[4]) for row in rows)
    return page(
        [
            heading(f"loading diary {start.isoformat()}..{end.isoformat()}"),
            pairs([("loads", str(len(rows))), ("tonnes", f"{tonnes:.2f}")]),
            table_block(
                "to load",
                [
                    Column("shipment"),
                    Column("wanted"),
                    Column("contract"),
                    Column("lot"),
                    Column("tonnes", Align.RIGHT),
                    Column("state"),
                    Column("vehicle"),
                ],
                rows,
            ),
            [] if rows else ["the diary is empty."],
        ]
    )


def cover_page(book: Book) -> str:
    """Malt in hand against malt promised, and the lots nothing can take.

    The two figures at the top are the ones the desk reads before signing
    anything, and they are deliberately not added together. Malt on the
    floor is four days off and might come off out of specification.
    """
    where = cover(book)
    orphans = orphan_lots(book)
    rows = []
    for lot in list_lots(book, certified=True):
        free = availability(book, lot.code)
        if free.empty:
            continue
        serves = contracts_a_lot_could_serve(book, lot.code)
        rows.append(
            [
                lot.code,
                lot.variety or "mixed",
                f"{free.free_tonnes:.2f}",
                str(len(serves)),
                ", ".join(contract.code for contract in serves) or "NOTHING",
            ]
        )
    return page(
        [
            heading("cover"),
            pairs(
                [
                    ("sealed in bins", f"{where.sealed_tonnes:.2f}"),
                    ("free to sell", f"{where.free_tonnes:.2f}"),
                    ("coming off the floor", f"{where.coming_tonnes:.2f}"),
                    ("promised", f"{where.outstanding_tonnes:.2f}"),
                    ("short by", f"{where.short_by:.2f}"),
                    ("short with the floor", f"{where.short_by_with_the_floor:.2f}"),
                ]
            ),
            ["everything signed could be served out of the bins today."] if where.covered else [],
            table_block(
                "lots nothing can take",
                [Column("lot"), Column("variety"), Column("free", Align.RIGHT)],
                [[code, "", ""] for code in orphans],
            ),
            table_block(
                "what each lot could serve",
                [
                    Column("lot"),
                    Column("variety"),
                    Column("free", Align.RIGHT),
                    Column("contracts", Align.RIGHT),
                    Column("which"),
                ],
                rows,
            ),
            [] if rows else ["there is no certified malt with anything left on it."],
        ]
    )
