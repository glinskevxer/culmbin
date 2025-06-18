"""A book with a plant, a variety and the three recipes in it."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.model.enums import Approval, Habit, KilnPhase, LegKind, MaltStyle, VesselKind
from culmbin.model.plant import Vessel
from culmbin.model.variety import Variety
from culmbin.process.germination import Schedule
from culmbin.process.kiln import Curve, KilnStep
from culmbin.process.steep import Programme, SteepLeg
from culmbin.store.book import Book
from culmbin.store.recipes import save_curve, save_programme, save_schedule
from culmbin.store.varieties import add_variety
from culmbin.store.vessels import add_vessel

BUILT = dt.date(1998, 4, 1)


@pytest.fixture
def plant(book: Book) -> Book:
    """Two steeps, two boxes, a floor, two kilns and a pale ale recipe set.

    The boxes are sized for the steeps on purpose. A 45 tonne charge of
    barley comes out of the steep at about 72 tonnes, because it is half as
    heavy again in water, and a box that only takes the barley weight is a
    box that cannot take the piece.
    """
    add_variety(
        book, Variety("LAUR", "Laureate", Habit.SPRING, Approval.APPROVED, dt.date(2018, 12, 1))
    )
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
