"""The quality page: complaints, and what could not be looked into.

The untraceable block is the reason this page exists. Counting complaints is
easy and it flatters, because the ones that can be walked back are the ones
somebody could do something about. The ones with no shipment against them
are the ones where the customer rang up about "the malt you sent in March",
and they are the ones a quality meeting quietly leaves out.

So they are at the top, with the open ones, and the counts underneath.
"""

from __future__ import annotations

import datetime as dt

from culmbin.model.complaint import Complaint
from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.complaints import (
    count_by_kind,
    list_complaints,
    open_complaints,
    untraceable,
)
from culmbin.units.season import Window


def _row(complaint: Complaint, on: dt.date) -> list[str]:
    """One complaint, as the page prints it."""
    return [
        complaint.code,
        complaint.customer,
        str(complaint.kind),
        complaint.raised.isoformat(),
        complaint.shipment or "",
        str(complaint.days_open(on)),
        str(complaint.state),
    ]


COLUMNS = [
    Column("complaint"),
    Column("customer"),
    Column("about"),
    Column("raised"),
    Column("shipment"),
    Column("days", Align.RIGHT),
    Column("state"),
]


def quality_page(book: Book, window: Window, on: dt.date) -> str:
    """Every complaint over a stretch of days, worst first."""
    raised = list_complaints(book, since=window.start, until=window.end)
    counts = count_by_kind(book, since=window.start)
    upheld = [item for item in raised if item.state.value == "upheld"]
    return page(
        [
            heading(f"complaints {window}"),
            pairs(
                [
                    ("raised", str(len(raised))),
                    ("open now", str(len(open_complaints(book)))),
                    ("upheld", str(len(upheld))),
                    ("cannot be traced", str(len(untraceable(book)))),
                ]
            ),
            table_block(
                "no shipment to walk back to",
                COLUMNS,
                [_row(item, on) for item in untraceable(book)],
            ),
            table_block(
                "still open",
                COLUMNS,
                [_row(item, on) for item in open_complaints(book)],
            ),
            table_block(
                "by kind",
                [Column("about"), Column("raised", Align.RIGHT)],
                [[str(kind), str(total)] for kind, total in counts.items()],
            ),
            table_block("everything raised", COLUMNS, [_row(item, on) for item in raised]),
            [] if raised else ["nobody has complained."],
        ]
    )
