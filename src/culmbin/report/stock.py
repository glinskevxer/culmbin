"""The stock pages: what malt is on site and what can be sold.

`stock_page` is the sales desk's first question every morning, and the
column that matters is not how much malt there is. It is how much is *free*:
sealed, certified, and not already spoken for by a shipment sitting in the
loading diary.

`laboratory_page` is the other end of the same problem. A lot with no
certificate cannot be sold, so a long list here is malt in bins that is not
stock at all.
"""

from __future__ import annotations

from culmbin.model.enums import BinState
from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.sales.desk import availability
from culmbin.store.bins import contents_of, list_bins
from culmbin.store.book import Book
from culmbin.store.lots import list_lots, uncertified


def stock_page(book: Book) -> str:
    """Every lot, with what is free on it."""
    rows = []
    total = 0.0
    free_total = 0.0
    for lot in list_lots(book):
        free = availability(book, lot.code)
        total += lot.tonnes
        free_total += free.free_tonnes
        rows.append(
            [
                lot.code,
                lot.bin_code,
                lot.variety or "mixed",
                str(lot.style) if lot.style else "",
                f"{lot.tonnes:.2f}",
                f"{free.free_tonnes:.2f}",
                "yes" if lot.certified else "NO",
            ]
        )
    return page(
        [
            heading("malt stock"),
            pairs(
                [
                    ("lots", str(len(rows))),
                    ("sealed tonnes", f"{total:.2f}"),
                    ("free tonnes", f"{free_total:.2f}"),
                ]
            ),
            table_block(
                "lots",
                [
                    Column("lot"),
                    Column("bin"),
                    Column("variety"),
                    Column("style"),
                    Column("sealed", Align.RIGHT),
                    Column("free", Align.RIGHT),
                    Column("certified"),
                ],
                rows,
            ),
            [] if rows else ["there is no malt in stock."],
        ]
    )


def bin_page(book: Book) -> str:
    """Every bin, what is in it, and whether it is mixed.

    The mixed column is the one to read. A mixed bin cannot serve a contract
    that names a variety however good the malt in it is, so a plant with
    half its bins marked is a plant that has lost half its contract cover.
    """
    rows = []
    mixed = 0
    for malt_bin in list_bins(book):
        held = contents_of(book, malt_bin.code)
        if malt_bin.mixed:
            mixed += 1
        rows.append(
            [
                malt_bin.code,
                str(malt_bin.state),
                f"{held.tonnes:.2f}",
                f"{malt_bin.capacity_tonnes:.1f}",
                f"{held.moisture:.2f}" if not held.empty else "",
                held.variety or ("mixed" if held.varieties else ""),
                "MIXED" if malt_bin.mixed else "",
            ]
        )
    empty = [row for row in rows if row[1] == BinState.EMPTY.value]
    return page(
        [
            heading("malt bins"),
            pairs(
                [
                    ("bins", str(len(rows))),
                    ("empty", str(len(empty))),
                    ("marked mixed", str(mixed)),
                ]
            ),
            table_block(
                "bins",
                [
                    Column("bin"),
                    Column("state"),
                    Column("holds", Align.RIGHT),
                    Column("capacity", Align.RIGHT),
                    Column("moisture", Align.RIGHT),
                    Column("variety"),
                    Column("segregation"),
                ],
                rows,
            ),
            [] if rows else ["there are no bins."],
        ]
    )


def laboratory_page(book: Book) -> str:
    """Every sealed lot with no certificate against it.

    A long list here is malt in bins that cannot be sold, which is different
    from malt that is not there.
    """
    rows = [
        [
            lot.code,
            lot.bin_code,
            lot.sealed.isoformat(),
            f"{lot.tonnes:.2f}",
            lot.variety or "mixed",
        ]
        for lot in uncertified(book)
    ]
    waiting = sum(float(row[3]) for row in rows)
    return page(
        [
            heading("waiting on the laboratory"),
            pairs([("lots", str(len(rows))), ("tonnes", f"{waiting:.2f}")]),
            table_block(
                "uncertified lots",
                [
                    Column("lot"),
                    Column("bin"),
                    Column("sealed"),
                    Column("tonnes", Align.RIGHT),
                    Column("variety"),
                ],
                rows,
            ),
            [] if rows else ["every lot has a certificate."],
        ]
    )
