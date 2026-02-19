"""When a vessel was last cleaned, and whether it is overdue."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import PieceStage, Role
from culmbin.model.party import Party
from culmbin.process.floor import cast, charge
from culmbin.store.book import Book
from culmbin.store.cleaning import (
    DEFAULT_DAYS,
    DEFAULT_PIECES,
    cleanings,
    interval_for,
    last_cleaned,
    overdue,
    pieces_since_cleaning,
    record_cleaning,
    set_interval,
    standing,
)
from culmbin.store.parties import add_party
from tests.support.records import a_piece

CLEANED = dt.date(2025, 11, 1)
TODAY = dt.date(2025, 11, 15)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


@pytest.fixture
def cleaners(plant: Book) -> Book:
    add_party(plant, Party("DKEHOE", "D Kehoe", Role.HAULIER, dt.date(2011, 6, 1)))
    return plant


def test_a_vessel_with_no_interval_takes_the_plant_default(cleaners: Book) -> None:
    interval = interval_for(cleaners, "S1")
    assert interval.days == DEFAULT_DAYS
    assert interval.pieces == DEFAULT_PIECES


def test_an_interval_can_be_set_and_moved(cleaners: Book) -> None:
    set_interval(cleaners, "S1", 14, 6)
    assert interval_for(cleaners, "S1").days == 14
    set_interval(cleaners, "S1", 21, 8)
    assert interval_for(cleaners, "S1").pieces == 8


def test_an_interval_of_nothing_is_refused(cleaners: Book) -> None:
    with pytest.raises(ConflictError, match="cannot be cleaned"):
        set_interval(cleaners, "S1", 0, 6)


def test_an_interval_on_a_vessel_that_is_not_there_is_refused(cleaners: Book) -> None:
    with pytest.raises(NotFoundError):
        set_interval(cleaners, "S9", 14, 6)


def test_a_vessel_nobody_has_cleaned_is_overdue(cleaners: Book) -> None:
    """Never cleaned is overdue, and it says so rather than reading as fine."""
    where = standing(cleaners, "S1")
    assert where.never_cleaned
    assert where.overdue(TODAY)
    assert "never been cleaned" in where.why(TODAY)


def test_a_cleaning_takes_it_off_the_list(cleaners: Book) -> None:
    record_cleaning(cleaners, "S1", CLEANED, "DKEHOE", "hot wash and rinse")
    where = standing(cleaners, "S1")
    assert not where.overdue(dt.date(2025, 11, 10))
    assert where.last_cleaned == CLEANED
    assert "inside its interval" in where.why(dt.date(2025, 11, 10))


def test_the_days_half_comes_due_on_its_own(cleaners: Book) -> None:
    set_interval(cleaners, "S1", 7, 100)
    record_cleaning(cleaners, "S1", CLEANED, "DKEHOE")
    where = standing(cleaners, "S1")
    assert where.overdue(dt.date(2025, 11, 8))
    assert "14 days against 7" in where.why(TODAY)


def test_the_pieces_half_comes_due_on_its_own(cleaners: Book) -> None:
    """A box run flat out for a fortnight is due on pieces, not on days."""
    set_interval(cleaners, "S1", 365, 1)
    record_cleaning(cleaners, "S1", CLEANED, "DKEHOE")
    charge(cleaners, a_piece("2025-118"), PROGRAMME, SCHEDULE, CURVE)
    where = standing(cleaners, "S1")
    assert where.overdue(dt.date(2025, 11, 4))
    assert "pieces against 1" in where.why(dt.date(2025, 11, 4))


def test_an_idle_vessel_is_due_on_days_for_a_different_reason(cleaners: Book) -> None:
    set_interval(cleaners, "S1", 7, 100)
    record_cleaning(cleaners, "S1", CLEANED, "DKEHOE")
    where = standing(cleaners, "S1")
    assert where.pieces_since == 0
    assert where.overdue(TODAY)


def test_the_pieces_are_counted_from_the_last_cleaning(cleaners: Book) -> None:
    """A piece charged before the clean is on the other side of it."""
    charge(cleaners, a_piece("2025-118"), PROGRAMME, SCHEDULE, CURVE)
    assert pieces_since_cleaning(cleaners, "S1") == 1
    record_cleaning(cleaners, "S1", dt.date(2025, 11, 4), "DKEHOE")
    assert pieces_since_cleaning(cleaners, "S1") == 0
    charge(
        cleaners,
        a_piece("2025-119", started=dt.date(2025, 11, 6)),
        PROGRAMME,
        SCHEDULE,
        CURVE,
        share=True,
    )
    assert pieces_since_cleaning(cleaners, "S1") == 1


def test_a_box_counts_the_pieces_cast_into_it(cleaners: Book) -> None:
    charge(cleaners, a_piece("2025-118"), PROGRAMME, SCHEDULE, CURVE)
    cast(cleaners, "2025-118", "G1", dt.date(2025, 11, 5), 71.8, 44.8, depth_cm=85.0)
    assert pieces_since_cleaning(cleaners, "G1") == 1


def test_the_cleanings_come_back_oldest_first(cleaners: Book) -> None:
    record_cleaning(cleaners, "S1", CLEANED, "DKEHOE", "hot wash")
    record_cleaning(cleaners, "S1", dt.date(2025, 11, 20), "DKEHOE", "hot wash and rinse")
    records = cleanings(cleaners, "S1")
    assert [day for day, _, _ in records] == [CLEANED, dt.date(2025, 11, 20)]
    assert records[1][2] == "hot wash and rinse"


def test_a_vessel_that_was_never_cleaned_has_no_date(cleaners: Book) -> None:
    assert last_cleaned(cleaners, "S1") is None
    assert cleanings(cleaners, "S1") == ()


def test_the_overdue_list_is_every_vessel_past_its_interval(cleaners: Book) -> None:
    for code in ("S1", "S2", "G1", "G2", "F1", "K1", "K2"):
        record_cleaning(cleaners, code, CLEANED, "DKEHOE")
    set_interval(cleaners, "S1", 7, 100)
    codes = [item.vessel for item in overdue(cleaners, TODAY)]
    assert codes == ["S1"]


def test_a_plant_nobody_has_cleaned_is_entirely_overdue(cleaners: Book) -> None:
    assert len(overdue(cleaners, TODAY)) == 7


def test_asking_about_a_vessel_that_is_not_there_is_refused(cleaners: Book) -> None:
    with pytest.raises(NotFoundError, match="S9"):
        standing(cleaners, "S9")


def test_a_cleaning_by_somebody_not_in_the_register_is_refused(cleaners: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        record_cleaning(cleaners, "S1", CLEANED, "NOBODY")


def test_the_days_since_are_never_negative(cleaners: Book) -> None:
    record_cleaning(cleaners, "S1", CLEANED, "DKEHOE")
    assert standing(cleaners, "S1").days_since(dt.date(2025, 10, 1)) == 0


def test_a_vessel_never_cleaned_has_no_days_since(cleaners: Book) -> None:
    assert standing(cleaners, "S1").days_since(TODAY) is None


def test_a_piece_stage_is_what_puts_a_vessel_on_the_count(cleaners: Book) -> None:
    charge(cleaners, a_piece("2025-118"), PROGRAMME, SCHEDULE, CURVE)
    assert standing(cleaners, "S1").pieces_since == 1
    assert PieceStage.STEEPING.value in str(PieceStage.STEEPING)
