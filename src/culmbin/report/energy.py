"""The gas page: what was burnt, and which runs can be compared.

The page is laid out to stop the wrong reading. Specific energy is the
figure everybody quotes and it is the one that moves when the pieces come in
wetter, so it is on the right and efficiency is on the left.

The two blocks above the table are the ones that decide whether the monthly
figure means anything at all. A month with runs nobody metered has a gas
number over a tonnage that includes malt the meter never saw, and a month
with a run at two hundred percent has an average that one bad reading has
moved further than a year of real work.
"""

from __future__ import annotations

from culmbin.process.energy import KilnEnergy
from culmbin.report.layout import Align, Column, heading, note, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.energy import kiln_of, list_runs, unmetered
from culmbin.units.season import Window


def _row(book: Book, run: KilnEnergy) -> list[str]:
    """One run, as the page prints it."""
    return [
        run.piece,
        kiln_of(book, run.piece),
        f"{run.green_moisture:.1f}",
        f"{run.malt_tonnes:.2f}",
        f"{run.water_kg / 1000.0:.2f}",
        f"{run.gas_m3:.0f}",
        f"{run.efficiency * 100:.0f}%",
        f"{run.specific_energy_kwh_per_tonne:.0f}",
    ]


def energy_page(book: Book, window: Window) -> str:
    """Every kiln run over a stretch of days, with the suspect ones marked."""
    runs = [run for run in list_runs(book, since=window.start, until=window.end) if run.gas_m3 > 0]
    waiting = unmetered(book)
    suspect = [run for run in runs if run.suspect]
    malt = sum(run.malt_tonnes for run in runs)
    gas = sum(run.gas_m3 for run in runs)
    heat = sum(run.heat_burnt_mj for run in runs)
    columns = [
        Column("piece"),
        Column("kiln"),
        Column("cast at", Align.RIGHT),
        Column("malt", Align.RIGHT),
        Column("water t", Align.RIGHT),
        Column("gas m3", Align.RIGHT),
        Column("efficiency", Align.RIGHT),
        Column("kWh/t", Align.RIGHT),
    ]
    facts = [
        ("runs metered", str(len(runs))),
        ("runs unmetered", str(len(waiting))),
        ("malt kilned", f"{malt:.2f}"),
        ("gas burnt", f"{gas:.0f}"),
    ]
    if malt > 0.0:
        facts.append(("kWh a tonne", f"{heat / 3.6 / malt:.0f}"))
    return page(
        [
            heading(f"kiln gas {window}"),
            pairs(facts),
            table_block(
                "outside what a kiln can do",
                columns,
                [_row(book, run) for run in suspect],
            ),
            table_block("runs", columns, [_row(book, run) for run in runs]),
            ["nobody metered anything."] if not runs else [],
            note(
                "efficiency is the number to compare. kWh a tonne carries the cast",
                "moisture with it, so a wet month reads worse without anything",
                "having got worse.",
                when=bool(runs),
            ),
        ]
    )
