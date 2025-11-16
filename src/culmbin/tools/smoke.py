"""A walk for a machine that has just installed the wheel, in a temporary book.

This is what runs after `pip install culmbin` in CI, and it is deliberately
not the same as the long walk in the workflow. That one exercises every
command. This one asks a much narrower question: does an installed wheel,
with no source tree next to it and no test fixtures, open a book and get a
lorry load of barley all the way to a certificate.

It writes into a temporary directory and takes it away afterwards, so it can
be run anywhere including on a machine with no writable working directory.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from culmbin.intake.desk import grade_load, settle_load, take_sample, weigh_in
from culmbin.intake.standard import Standard
from culmbin.model.enums import Approval, Basis, Habit, Material, Role
from culmbin.model.intake import Delivery, Purchase
from culmbin.model.party import Party
from culmbin.model.results import Result, analysis_of
from culmbin.model.variety import Variety
from culmbin.store.book import Book
from culmbin.store.migrations import migrate
from culmbin.store.parties import add_party
from culmbin.store.purchases import add_purchase, outstanding
from culmbin.store.standards import add_standard
from culmbin.store.varieties import add_variety
from culmbin.units.season import Window

ARRIVED = dt.date(2025, 9, 18)
STAMP = "2025-09-18T00:00:00+00:00"


def walk(book: Book) -> list[str]:
    """Take one lorry from the weighbridge to a settlement, saying each step."""
    said = []
    add_party(book, Party("HOLB", "Holbeach Grange", Role.GROWER, dt.date(2011, 6, 1)))
    add_variety(
        book, Variety("LAUR", "Laureate", Habit.SPRING, Approval.APPROVED, dt.date(2018, 12, 1))
    )
    add_standard(book, Standard("malting 2025"))
    add_purchase(
        book,
        Purchase(
            code="P-1",
            party="HOLB",
            variety="LAUR",
            crop_year=2025,
            tonnes=480.0,
            window=Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30)),
            standard="malting 2025",
            price_per_tonne=Decimal("232.50"),
            signed=dt.date(2025, 3, 12),
        ),
    )
    said.append("registers written")
    weigh_in(
        book,
        Delivery(
            ticket="W-1",
            purchase="P-1",
            party="HOLB",
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
            harvested=dt.date(2025, 8, 14),
        ),
    )
    said.append("lorry weighed in")
    take_sample(
        book,
        "W-1",
        analysis_of(
            "B-1",
            Material.BARLEY,
            ARRIVED,
            [
                Result("moisture", 12.5),
                Result("screenings", 1.4),
                Result("germ_capacity", 99.0),
                Result("germ_energy", 98.0),
                Result("admixture", 0.4),
                Result("nitrogen", 1.62, Basis.DRY),
            ],
        ),
    )
    said.append("sample recorded")
    grading = grade_load(book, "W-1", dt.date(2025, 9, 19))
    said.append(f"graded {grading.outcome}, {grading.settled_tonnes:.3f}t settled")
    settlement = settle_load(book, "W-1")
    if settlement is None:  # pragma: no cover
        raise SystemExit("smoke: a clean load was rejected")
    said.append(f"settled at {settlement.value}")
    said.append(f"{outstanding(book, 'P-1'):.2f}t still to come on P-1")
    return said


def main(argv: list[str] | None = None) -> int:
    """Run the walk in a temporary book and say what happened."""
    parser = argparse.ArgumentParser(description="walk an installed wheel")
    parser.add_argument("--quiet", action="store_true", help="say only whether it worked")
    arguments = parser.parse_args(argv)
    with (
        tempfile.TemporaryDirectory() as directory,
        Book.open(Path(directory) / "smoke.sqlite3") as book,
    ):
        migrate(book, STAMP)
        said = walk(book)
    if not arguments.quiet:
        for line in said:
            print(f"smoke: {line}")
    print("smoke: the wheel works.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
