"""The steep water page: metered, kept, and gone to drain.

Three numbers and only the last one is what the effluent bill is on. They
are next to each other because the first is the one everybody quotes and the
third is the one that costs money, and putting them apart lets a plant
congratulate itself on a meter reading.
"""

from __future__ import annotations

from culmbin.process.water import TYPICAL_HIGH, TYPICAL_LOW
from culmbin.report.layout import Align, Column, heading, note, page, pairs, table
from culmbin.store.book import Book
from culmbin.store.water import heavy, list_water, metered, to_drain
from culmbin.units.season import Window


def water_page(book: Book, window: Window) -> str:
    """Every steep metered over a stretch of days, and what went to drain."""
    uses = list_water(book, window.start, window.end)
    rows = [
        [
            use.piece,
            f"{use.metered_m3:.1f}",
            f"{use.taken_up_m3:.1f}",
            f"{use.to_drain_m3:.1f}",
            f"{use.drain_share * 100:.0f}%",
            f"{use.specific_m3_per_tonne:.2f}",
        ]
        for use in uses
    ]
    return page(
        [
            heading(f"steep water {window}"),
            pairs(
                [
                    ("steeps metered", str(len(uses))),
                    ("metered", f"{metered(book, window.start, window.end):.1f} m3"),
                    ("to drain", f"{to_drain(book, window.start, window.end):.1f} m3"),
                    ("over the band", str(len(heavy(book, window.start)))),
                ]
            ),
            table(
                [
                    Column("piece"),
                    Column("metered", Align.RIGHT),
                    Column("kept", Align.RIGHT),
                    Column("to drain", Align.RIGHT),
                    Column("share", Align.RIGHT),
                    Column("m3 a tonne", Align.RIGHT),
                ],
                rows,
            )
            if rows
            else [],
            note("nobody metered a steep.", when=not rows),
            note(
                f"a plant with air rests and recycling runs {TYPICAL_LOW:.0f} to "
                f"{TYPICAL_HIGH:.0f} cubic metres a tonne.",
                "over the band is a bill rather than a fault.",
                when=bool(rows),
            ),
        ]
    )
