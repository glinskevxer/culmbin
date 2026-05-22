"""The month end page: one walk from the weighbridge to the loading bay.

It is the only page in the package that is laid out as a balance rather than
as a list, because that is what somebody is doing when they read it: taking
one number off another and asking what the difference is made of.

Everything on the left is as it lies and everything on the right is dry
matter, and the two columns are next to each other on purpose. The dry
matter column is the one that adds up across the building. The wet column is
the one every other page in the building is written in.
"""

from __future__ import annotations

from culmbin.process.reconcile import drawn_against_charged, reconcile
from culmbin.report.layout import Align, Column, heading, page, table_block
from culmbin.store.book import Book
from culmbin.store.energy import gas_used
from culmbin.store.shipments import list_shipments
from culmbin.store.water import metered, to_drain
from culmbin.units.mass import dry_matter
from culmbin.units.season import Window


def month_page(book: Book, window: Window) -> str:
    """The whole month as a balance, with the gaps underneath."""
    walk = reconcile(book, window)
    gap = drawn_against_charged(book, window)
    gone = [
        shipment
        for shipment in list_shipments(book, since=window.start, until=window.end)
        if shipment.counts
    ]
    shipped = sum(shipment.tonnes for shipment in gone)
    shipped_dry = sum(dry_matter(item.tonnes, item.moisture) for item in gone)
    rows = [
        ["barley graded", f"{walk.graded_tonnes:.2f}", ""],
        ["barley tipped into silo", f"{walk.tipped_tonnes:.2f}", ""],
        ["barley charged to steep", f"{walk.charged_tonnes:.2f}", f"{walk.charged_dry:.2f}"],
        ["malt off the kiln", f"{walk.malt_tonnes:.2f}", f"{walk.malt_dry:.2f}"],
        ["culm to the feed merchant", f"{walk.culm_tonnes:.2f}", ""],
        ["malt despatched", f"{shipped:.2f}", f"{shipped_dry:.2f}"],
    ]
    figures = [
        ["malting loss", f"{walk.malting_loss:.2f}%"],
        ["yield", f"{walk.yield_percent:.2f}%"],
        ["culm as a share of the loss", f"{walk.culm_share:.2f}"],
        ["gas burnt", f"{gas_used(book, window.start, window.end):.0f} m3"],
        ["water metered", f"{metered(book, window.start, window.end):.0f} m3"],
        ["water to drain", f"{to_drain(book, window.start, window.end):.0f} m3"],
    ]
    gaps = [["barley in the pit", f"{walk.pit_gap:.2f}"]]
    if abs(gap) > 0.01:
        gaps.append(["charged without going through a silo", f"{gap:.2f}"])
    return page(
        [
            heading(f"month end {window}"),
            table_block(
                "the walk",
                [
                    Column("stage"),
                    Column("as it lies", Align.RIGHT),
                    Column("dry matter", Align.RIGHT),
                ],
                rows,
            ),
            table_block(
                "figures",
                [Column("what"), Column("value", Align.RIGHT)],
                figures,
            ),
            table_block("gaps", [Column("what"), Column("tonnes", Align.RIGHT)], gaps),
            list(walk.notes()),
            [
                "the dry matter column is the one that adds up across the building.",
                "the wet column is the one every other page is written in.",
            ],
        ]
    )
