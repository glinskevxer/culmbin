"""The barley yard page: what is in the silos and what is still in the pit.

The pit list goes at the top. A load that has been graded and not tipped is
barley sitting in the intake pit, and the pit is where barley goes bad, so
it is the thing on this page that has a clock running on it.

The silo table carries the segregation mark for the same reason the bin page
does: a mixed silo cannot charge a piece at all, so a yard with half its
silos marked has half the barley it thinks it has.
"""

from __future__ import annotations

from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.deliveries import get_delivery
from culmbin.store.silos import holding_in, list_silos, untipped


def yard_page(book: Book) -> str:
    """Every silo, what is in it, and every load still in the pit."""
    rows = []
    held = 0.0
    mixed = 0
    for silo in list_silos(book):
        holding = holding_in(book, silo.code)
        held += holding.tonnes
        if silo.mixed:
            mixed += 1
        rows.append(
            [
                silo.code,
                f"{holding.tonnes:.2f}",
                f"{silo.capacity_tonnes:.0f}",
                f"{holding.moisture:.2f}" if not holding.empty else "",
                holding.variety or ("mixed" if holding.varieties else ""),
                str(holding.crop_year) if holding.crop_year else "",
                str(len(holding.shares)),
                "MIXED" if silo.mixed else "",
            ]
        )
    pit = []
    for ticket in untipped(book):
        delivery = get_delivery(book, ticket)
        pit.append(
            [ticket, delivery.party, delivery.arrived.isoformat(), f"{delivery.net_tonnes:.2f}"]
        )
    return page(
        [
            heading("barley yard"),
            pairs(
                [
                    ("silos", str(len(rows))),
                    ("tonnes held", f"{held:.2f}"),
                    ("marked mixed", str(mixed)),
                    ("waiting in the pit", str(len(pit))),
                ]
            ),
            table_block(
                "still in the pit",
                [
                    Column("ticket"),
                    Column("grower"),
                    Column("arrived"),
                    Column("weighed", Align.RIGHT),
                ],
                pit,
            ),
            table_block(
                "silos",
                [
                    Column("silo"),
                    Column("holds", Align.RIGHT),
                    Column("capacity", Align.RIGHT),
                    Column("moisture", Align.RIGHT),
                    Column("variety"),
                    Column("crop", Align.RIGHT),
                    Column("loads", Align.RIGHT),
                    Column("segregation"),
                ],
                rows,
            ),
            [] if rows else ["there are no silos."],
        ]
    )
