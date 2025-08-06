"""Fixtures every test directory shares.

The important one is `book`, and the important thing about it is that it
closes. An unclosed sqlite connection is silence on 3.12 and a
`ResourceWarning` on 3.13, blamed on whichever test the collector happened
to be running when the garbage collector got round to it, which is never the
test that opened it.

`registers` and `plant` are here rather than in a directory conftest because
two directories wanted them and each had written its own, which is how the
report tests ended up with an autouse fixture that added a variety the floor
fixture was also adding.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest

from culmbin.intake.standard import Standard
from culmbin.model.enums import Approval, Habit, KilnPhase, LegKind, MaltStyle, VesselKind
from culmbin.model.plant import Vessel
from culmbin.model.variety import Variety
from culmbin.process.germination import Schedule
from culmbin.process.kiln import Curve, KilnStep
from culmbin.process.steep import Programme, SteepLeg
from culmbin.store.book import MEMORY, Book
from culmbin.store.migrations import migrate
from culmbin.store.recipes import save_curve, save_programme, save_schedule
from culmbin.store.standards import add_standard
from culmbin.store.varieties import add_variety
from culmbin.store.vessels import add_vessel

APPLIED_AT = "2025-07-01T08:00:00+00:00"
TODAY = dt.date(2025, 11, 4)
BUILT = dt.date(1998, 4, 1)
LISTED = dt.date(2018, 12, 1)


@pytest.fixture
def book() -> Iterator[Book]:
    """An empty book at the current schema version."""
    with Book.open(MEMORY) as opened:
        migrate(opened, APPLIED_AT)
        yield opened


@pytest.fixture
def registers(book: Book) -> Book:
    """The two varieties and the intake standard nearly every test needs."""
    add_variety(book, Variety("LAUR", "Laureate", Habit.SPRING, Approval.APPROVED, LISTED))
    add_variety(book, Variety("DIAB", "Diablo", Habit.SPRING, Approval.APPROVED, LISTED))
    add_standard(book, Standard("malting 2025"))
    return book


@pytest.fixture
def plant(registers: Book) -> Book:
    """Two steeps, two boxes, a floor, two kilns and a pale ale recipe set.

    The boxes are sized for the steeps on purpose. A 45 tonne charge of
    barley comes out of the steep at about 72 tonnes, because it is half as
    heavy again in water, and a box that only takes the barley weight is a
    box that cannot take the piece.
    """
    book = registers
    for code in ("S1", "S2"):
        add_vessel(
            book, Vessel(code, f"steep {code}", VesselKind.STEEP, BUILT, charge_limit_t=45.0)
        )
    for code in ("G1", "G2"):
        add_vessel(
            book,
            Vessel(
                code,
                f"box {code}",
                VesselKind.BOX,
                BUILT,
                floor_area_m2=170.0,
                depth_limit_cm=90.0,
            ),
        )
    add_vessel(
        book,
        Vessel(
            "F1", "old floor", VesselKind.FLOOR, BUILT, floor_area_m2=300.0, depth_limit_cm=30.0
        ),
    )
    for code in ("K1", "K2"):
        add_vessel(
            book,
            Vessel(
                code,
                f"kiln {code}",
                VesselKind.KILN,
                BUILT,
                floor_area_m2=140.0,
                depth_limit_cm=100.0,
            ),
        )
    save_programme(
        book,
        Programme(
            "pale ale two stand",
            MaltStyle.PALE_ALE,
            (
                SteepLeg(LegKind.WET_STAND, 8.0, 14.0),
                SteepLeg(LegKind.AIR_REST, 16.0, 16.0),
                SteepLeg(LegKind.WET_STAND, 6.0, 14.0),
            ),
            44.5,
        ),
    )
    save_programme(
        book,
        Programme(
            "lager long steep",
            MaltStyle.LAGER,
            (SteepLeg(LegKind.WET_STAND, 30.0, 12.0),),
            42.0,
        ),
    )
    save_schedule(
        book, Schedule("pale ale four day", MaltStyle.PALE_ALE, 1200.0, (200.0, 500.0, 800.0))
    )
    save_curve(
        book,
        Curve(
            "pale ale 18 hour",
            MaltStyle.PALE_ALE,
            (
                KilnStep(KilnPhase.FREE_DRYING, 10.0, 60.0),
                KilnStep(KilnPhase.BREAK, 4.0, 70.0),
                KilnStep(KilnPhase.CURING, 4.0, 85.0),
            ),
            4.2,
        ),
    )
    return book
