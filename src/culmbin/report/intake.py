"""The intake pages: what came in, what is waiting, and what went back.

Two pages here and they answer different questions.

`day_sheet` is what the intake office reads in the morning. It opens with
the two queues, because those are the loads nothing can happen to until
somebody does something, and a page is read to the bottom once.

`rejection_page` is what the buyer takes to the telephone. It is loads that
went back, with the reason on each, because the first thing the grower asks
is why.
"""

from __future__ import annotations

import datetime as dt

from culmbin.intake.desk import summarise
from culmbin.model.enums import IntakeOutcome
from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.deliveries import get_delivery, list_deliveries, undated, unsampled
from culmbin.store.gradings import list_gradings, ungraded
from culmbin.units.season import Window


def _waiting_rows(book: Book, on: dt.date) -> list[list[str]]:
    """Every load that cannot move on, with what it is waiting for."""
    rows = []
    for delivery in unsampled(book, until=on):
        rows.append([delivery.ticket, delivery.party, delivery.arrived.isoformat(), "sample"])
    for ticket in ungraded(book, until=on):
        delivery = get_delivery(book, ticket)
        rows.append([ticket, delivery.party, delivery.arrived.isoformat(), "grading"])
    for delivery in undated(book):
        if delivery.arrived <= on:
            rows.append(
                [delivery.ticket, delivery.party, delivery.arrived.isoformat(), "harvest date"]
            )
    rows.sort(key=lambda row: (row[2], row[0], row[3]))
    return rows


def _graded_rows(book: Book, window: Window) -> list[list[str]]:
    """Every load graded in the window, newest last."""
    rows = []
    for grading in list_gradings(book, since=window.start, until=window.end):
        delivery = get_delivery(book, grading.ticket)
        rows.append(
            [
                grading.ticket,
                delivery.party,
                f"{grading.net_tonnes:.2f}",
                f"{grading.settled_tonnes:.2f}",
                f"{grading.price_adjustment}",
                str(grading.outcome),
            ]
        )
    return rows


def day_sheet(book: Book, window: Window, on: dt.date) -> str:
    """What the intake office reads in the morning.

    The queues go at the top. A load in the pit that has not been graded is
    barley we have taken in and cannot pay for, and it stops being anybody's
    problem the moment it drops off this page.
    """
    summary = summarise(book, window)
    waiting = _waiting_rows(book, on)
    return page(
        [
            heading(f"intake {window}"),
            pairs(
                [
                    ("as at", on.isoformat()),
                    ("loads graded", str(summary.loads)),
                    ("rejected", f"{summary.rejected} ({summary.rejection_rate:.0f}%)"),
                    ("net tonnes", f"{summary.net_tonnes:.2f}"),
                    ("settled tonnes", f"{summary.settled_tonnes:.2f}"),
                    ("shrinkage", f"{summary.shrinkage_tonnes:.2f}"),
                ]
            ),
            table_block(
                "waiting",
                [Column("ticket"), Column("grower"), Column("arrived"), Column("waiting for")],
                waiting,
            ),
            table_block(
                "graded",
                [
                    Column("ticket"),
                    Column("grower"),
                    Column("net", Align.RIGHT),
                    Column("settled", Align.RIGHT),
                    Column("off price", Align.RIGHT),
                    Column("outcome"),
                ],
                _graded_rows(book, window),
            ),
        ]
    )


def rejection_page(book: Book, window: Window) -> str:
    """Every load that went back over a stretch of days, with the reason.

    The reason is what the grower asks about first, so it is a column and
    not a footnote.
    """
    rows = []
    for grading in list_gradings(
        book, outcome=IntakeOutcome.REJECTED, since=window.start, until=window.end
    ):
        delivery = get_delivery(book, grading.ticket)
        rows.append(
            [
                grading.ticket,
                delivery.party,
                delivery.arrived.isoformat(),
                f"{grading.net_tonnes:.2f}",
                ", ".join(str(reason) for reason in grading.rejections),
            ]
        )
    return page(
        [
            heading(f"rejections {window}"),
            table_block(
                "loads sent back",
                [
                    Column("ticket"),
                    Column("grower"),
                    Column("arrived"),
                    Column("tonnes", Align.RIGHT),
                    Column("reasons"),
                ],
                rows,
            ),
            [] if rows else ["nothing went back."],
        ]
    )


def grower_page(book: Book, party: str, window: Window) -> str:
    """Every load from one grower over a stretch of days.

    This is the page that goes out with the statement, so it carries what
    arrived as well as what was settled: the grower's own weighbridge ticket
    says the first number and it is the second one he is paid on.
    """
    rows = []
    for delivery in list_deliveries(book, party=party, since=window.start, until=window.end):
        gradings = {
            grading.ticket: grading
            for grading in list_gradings(book, since=window.start, until=window.end)
        }
        grading = gradings.get(delivery.ticket)
        rows.append(
            [
                delivery.ticket,
                delivery.arrived.isoformat(),
                f"{delivery.net_tonnes:.2f}",
                "" if grading is None else f"{grading.settled_tonnes:.2f}",
                "not graded" if grading is None else str(grading.outcome),
            ]
        )
    return page(
        [
            heading(f"{party} intake {window}"),
            table_block(
                "deliveries",
                [
                    Column("ticket"),
                    Column("arrived"),
                    Column("weighed", Align.RIGHT),
                    Column("settled", Align.RIGHT),
                    Column("outcome"),
                ],
                rows,
            ),
            [] if rows else ["nothing was delivered."],
        ]
    )
