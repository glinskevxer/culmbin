"""The grower's statement: every load, what came off it, and what it is worth.

This is the one page in the package that goes to somebody outside the
building, so it is laid out to be argued with. Every deduction is a line
with its own reason on it, and the two weights are next to each other,
because the grower has his own weighbridge ticket and the first thing he
will do is compare them.

A rejected load is on the statement and is worth nothing. Leaving it off
would be tidier and it would also mean a lorry that went back does not
appear anywhere the grower can see, which is exactly the load he rings up
about.
"""

from __future__ import annotations

from decimal import Decimal

from culmbin.intake.desk import settle_load
from culmbin.report.layout import Align, Column, heading, money, note, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.deliveries import list_deliveries
from culmbin.store.gradings import find_grading
from culmbin.store.parties import get_party
from culmbin.units.season import Window


def statement_page(book: Book, party: str, window: Window) -> str:
    """Every load from one grower over a stretch of days, and what it came to."""
    found = get_party(book, party)
    loads = []
    lines = []
    total = Decimal("0.00")
    settled_tonnes = 0.0
    rejected = 0
    for delivery in list_deliveries(book, party=party, since=window.start, until=window.end):
        grading = find_grading(book, delivery.ticket)
        if grading is None:
            loads.append(
                [
                    delivery.ticket,
                    delivery.arrived.isoformat(),
                    f"{delivery.net_tonnes:.2f}",
                    "",
                    "",
                    "not graded",
                ]
            )
            continue
        if grading.rejected:
            rejected += 1
            loads.append(
                [
                    delivery.ticket,
                    delivery.arrived.isoformat(),
                    f"{delivery.net_tonnes:.2f}",
                    "0.00",
                    money("0.00", 10),
                    ", ".join(str(reason) for reason in grading.rejections),
                ]
            )
            continue
        settlement = settle_load(book, delivery.ticket)
        assert settlement is not None
        total += settlement.value
        settled_tonnes += settlement.settled_tonnes
        loads.append(
            [
                delivery.ticket,
                delivery.arrived.isoformat(),
                f"{delivery.net_tonnes:.2f}",
                f"{settlement.settled_tonnes:.2f}",
                money(str(settlement.value), 10),
                f"at {settlement.net_per_tonne}",
            ]
        )
        for adjustment in grading.adjustments:
            lines.append([delivery.ticket, adjustment.note, str(adjustment)])
    return page(
        [
            heading(f"statement for {found.name} {window}"),
            pairs(
                [
                    ("grower", f"{found}"),
                    ("holding", found.holding or ""),
                    ("loads", str(len(loads))),
                    ("rejected", str(rejected)),
                    ("settled tonnes", f"{settled_tonnes:.2f}"),
                    ("value", str(total)),
                ]
            ),
            table_block(
                "loads",
                [
                    Column("ticket"),
                    Column("arrived"),
                    Column("weighed", Align.RIGHT),
                    Column("settled", Align.RIGHT),
                    Column("value", Align.RIGHT),
                    Column("note"),
                ],
                loads,
            ),
            table_block(
                "deductions",
                [Column("ticket"), Column("why"), Column("what came off")],
                lines,
            ),
            note(
                "nothing was delivered.",
                when=not loads,
            ),
            note(
                "the weighed column is the lorry and the settled column is what the",
                "contract pays on. Every difference between them is a line above.",
                when=bool(loads),
            ),
        ]
    )
