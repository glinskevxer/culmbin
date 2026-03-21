"""The cleaning page: what is overdue and what nobody is policing.

The second block is the one worth having. A vessel with no interval set is
not policed at all, which is a decision somebody made once and nobody has
looked at since, and it looks identical on every other page to a vessel that
is clean.
"""

from __future__ import annotations

import datetime as dt

from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.cleaning import cleanings, interval_for, policed, standing
from culmbin.store.vessels import list_vessels


def cleaning_page(book: Book, on: dt.date) -> str:
    """Every vessel, when it was last cleaned, and whether it is overdue."""
    due = []
    unpoliced = []
    rows = []
    for vessel in list_vessels(book):
        where = standing(book, vessel.code)
        interval = interval_for(book, vessel.code)
        days = where.days_since(on)
        row = [
            vessel.code,
            str(vessel.kind),
            "" if where.last_cleaned is None else where.last_cleaned.isoformat(),
            "" if days is None else str(days),
            str(where.pieces_since),
            f"{interval.days}d / {interval.pieces}p",
            "yes" if policed(book, vessel.code) else "no",
        ]
        rows.append(row)
        if not policed(book, vessel.code):
            unpoliced.append(row)
        elif where.overdue(on):
            due.append([vessel.code, str(vessel.kind), where.why(on)])
    return page(
        [
            heading(f"cleaning as at {on.isoformat()}"),
            pairs(
                [
                    ("vessels", str(len(rows))),
                    ("overdue", str(len(due))),
                    ("nobody policing", str(len(unpoliced))),
                ]
            ),
            table_block(
                "overdue",
                [Column("vessel"), Column("kind"), Column("why")],
                due,
            ),
            table_block(
                "no interval set",
                [
                    Column("vessel"),
                    Column("kind"),
                    Column("last cleaned"),
                    Column("days", Align.RIGHT),
                    Column("pieces", Align.RIGHT),
                    Column("interval"),
                    Column("policed"),
                ],
                unpoliced,
            ),
            table_block(
                "every vessel",
                [
                    Column("vessel"),
                    Column("kind"),
                    Column("last cleaned"),
                    Column("days", Align.RIGHT),
                    Column("pieces", Align.RIGHT),
                    Column("interval"),
                    Column("policed"),
                ],
                rows,
            ),
            [] if rows else ["there is no plant."],
        ]
    )


def vessel_history(book: Book, vessel: str) -> str:
    """Every cleaning of one vessel, oldest first."""
    records = cleanings(book, vessel)
    return page(
        [
            heading(f"cleaning history for {vessel}"),
            table_block(
                "cleanings",
                [Column("on"), Column("by"), Column("note")],
                [[day.isoformat(), who, note] for day, who, note in records],
            ),
            [] if records else [f"{vessel} has never been cleaned."],
        ]
    )
