"""A walk for a machine that has just installed the wheel, in a temporary book.

This is what runs after `pip install culmbin` in CI, and it is deliberately
not the same as the long walk in the workflow. That one exercises every
command through the console script. This one asks a narrower question of the
library itself: does an installed wheel, with no source tree next to it and
no test fixtures, take one lorry load of barley all the way from the
weighbridge to a lorry going out of the gate.

It goes the whole way on purpose. Stopping at the settlement, which is where
it used to stop, exercised one package out of nine, and the packages it did
not reach are the ones with the arithmetic in them.

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
from culmbin.model.enums import (
    Approval,
    Basis,
    ContractState,
    Habit,
    KilnPhase,
    LegKind,
    MaltStyle,
    Material,
    Role,
    VesselKind,
)
from culmbin.model.intake import Delivery, Purchase
from culmbin.model.lots import Bin
from culmbin.model.party import Party
from culmbin.model.plant import Vessel
from culmbin.model.results import Result, analysis_of
from culmbin.model.sales import Contract
from culmbin.model.silo import Silo
from culmbin.model.spec import Clause, specification
from culmbin.model.variety import Variety
from culmbin.process.floor import balance_of, cast, load_kiln, strip_kiln
from culmbin.process.germination import Schedule
from culmbin.process.kiln import Curve, KilnStep
from culmbin.process.steep import Programme, SteepLeg
from culmbin.process.yard import charge_from_silo
from culmbin.sales.certificate import write
from culmbin.sales.desk import allocate, despatch, load
from culmbin.store.analyses import save_analysis
from culmbin.store.bins import add_bin, receive, seal
from culmbin.store.book import Book
from culmbin.store.contracts import add_contract, position
from culmbin.store.lots import certify, seal_lot
from culmbin.store.migrations import migrate
from culmbin.store.parties import add_party
from culmbin.store.purchases import add_purchase, outstanding
from culmbin.store.recipes import save_curve, save_programme, save_schedule
from culmbin.store.silos import add_silo, tip
from culmbin.store.specs import save_specification
from culmbin.store.standards import add_standard
from culmbin.store.varieties import add_variety
from culmbin.store.vessels import add_vessel
from culmbin.trace.walk import backward_from_shipment
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
    said.extend(_through_the_plant(book))
    return said


def _the_plant(book: Book) -> None:
    """A steep, a box, a kiln, a silo and one recipe of each kind."""
    built = dt.date(1998, 4, 1)
    add_vessel(book, Vessel("S1", "steep 1", VesselKind.STEEP, built, charge_limit_t=45.0))
    add_vessel(
        book,
        Vessel("G1", "box 1", VesselKind.BOX, built, floor_area_m2=170.0, depth_limit_cm=90.0),
    )
    add_vessel(
        book,
        Vessel("K1", "kiln 1", VesselKind.KILN, built, floor_area_m2=140.0, depth_limit_cm=100.0),
    )
    add_silo(book, Silo("SL1", 400.0))
    save_programme(
        book,
        Programme("p", MaltStyle.PALE_ALE, (SteepLeg(LegKind.WET_STAND, 8.0, 14.0),), 44.5),
    )
    save_schedule(book, Schedule("s", MaltStyle.PALE_ALE, 1200.0))
    save_curve(
        book,
        Curve(
            "c",
            MaltStyle.PALE_ALE,
            (
                KilnStep(KilnPhase.FREE_DRYING, 10.0, 60.0),
                KilnStep(KilnPhase.CURING, 4.0, 85.0),
            ),
            4.2,
        ),
    )


def _through_the_plant(book: Book) -> list[str]:
    """The rest of the chain: silo, steep, box, kiln, bin, lot, lorry out."""
    said = []
    _the_plant(book)
    tip(book, "SL1", "W-1", dt.date(2025, 9, 19))
    said.append("tipped into the silo")
    charge_from_silo(
        book,
        "2025-118",
        "SL1",
        "LAUR",
        2025,
        MaltStyle.PALE_ALE,
        20.0,
        "S1",
        dt.date(2025, 11, 3),
        "p",
        "s",
        "c",
    )
    said.append("charged out of the silo")
    cast(book, "2025-118", "G1", dt.date(2025, 11, 5), 31.9, 44.8, depth_cm=40.0)
    load_kiln(book, "2025-118", "K1", dt.date(2025, 11, 8))
    strip_kiln(book, "2025-118", dt.date(2025, 11, 9), 16.8, 4.4, 0.9)
    balance = balance_of(book, "2025-118")
    said.append(f"malting loss {balance.malting_loss:.2f}%")
    add_bin(book, Bin("B04", 220.0))
    receive(book, "B04", "2025-118", 16.8, 4.4, dt.date(2025, 11, 12))
    seal(book, "B04")
    seal_lot(book, "L-1", "B04", dt.date(2025, 11, 13))
    save_analysis(
        book,
        analysis_of(
            "M-1",
            Material.MALT,
            dt.date(2025, 11, 13),
            [
                Result("malt_moisture", 4.4),
                Result("extract_fine", 81.4, Basis.DRY),
                Result("colour", 3.4),
            ],
        ),
    )
    certify(book, "L-1", "M-1")
    said.append("lot sealed and certified")
    save_specification(
        book,
        specification(
            "lager 2025",
            Material.MALT,
            [Clause("extract_fine", basis=Basis.DRY, minimum=80.0), Clause("colour", maximum=5.0)],
        ),
    )
    _the_customer(book)
    add_contract(
        book,
        Contract(
            code="C-1",
            customer="BRWY",
            specification="lager 2025",
            tonnes=2400.0,
            moisture=4.5,
            price_per_tonne=Decimal("398.00"),
            window=Window(dt.date(2025, 10, 1), dt.date(2026, 9, 30)),
            signed=dt.date(2025, 6, 2),
            state=ContractState.SIGNED,
        ),
    )
    allocate(book, "S-1", "C-1", "L-1", 10.0, dt.date(2025, 11, 20))
    load(book, "S-1", 10.0, 4.4, dt.date(2025, 11, 20))
    despatch(book, "S-1")
    said.append(f"{position(book, 'C-1').delivered:.3f} contract tonnes despatched")
    walk = backward_from_shipment(book, "S-1")
    said.append(f"the shipment walks back to {', '.join(walk.growers)}")
    certificate = write(book, "L-1", dt.date(2025, 11, 21))
    said.append(f"the certificate is {len(certificate.splitlines())} lines")
    return said


def _the_customer(book: Book) -> None:
    """The one customer the walk sells to."""
    add_party(book, Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, dt.date(2016, 2, 1)))


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
