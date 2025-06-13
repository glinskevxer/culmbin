"""Programmes, schedules and curves in the book."""

from __future__ import annotations

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import KilnPhase, LegKind, MaltStyle
from culmbin.process.germination import Schedule
from culmbin.process.kiln import Curve, KilnStep
from culmbin.process.steep import Programme, SteepLeg
from culmbin.store.book import Book
from culmbin.store.recipes import (
    get_curve,
    get_programme,
    get_schedule,
    list_curves,
    list_programmes,
    list_schedules,
    recipes_for,
    save_curve,
    save_programme,
    save_schedule,
)


def programme(name: str = "pale ale two stand", style: MaltStyle = MaltStyle.PALE_ALE) -> Programme:
    return Programme(
        name=name,
        style=style,
        legs=(
            SteepLeg(LegKind.WET_STAND, 8.0, 14.0),
            SteepLeg(LegKind.AIR_REST, 16.0, 16.0),
            SteepLeg(LegKind.WET_STAND, 6.0, 14.0),
        ),
        target_moisture=44.5,
    )


def schedule(name: str = "pale ale four day", style: MaltStyle = MaltStyle.PALE_ALE) -> Schedule:
    return Schedule(
        name=name,
        style=style,
        target_degree_hours=1200.0,
        turns_at=(200.0, 500.0, 800.0),
    )


def curve(name: str = "pale ale 18 hour", style: MaltStyle = MaltStyle.PALE_ALE) -> Curve:
    return Curve(
        name=name,
        style=style,
        steps=(
            KilnStep(KilnPhase.FREE_DRYING, 10.0, 60.0),
            KilnStep(KilnPhase.BREAK, 4.0, 70.0),
            KilnStep(KilnPhase.CURING, 4.0, 85.0),
        ),
        target_moisture=4.2,
    )


def test_a_programme_reads_back_the_way_it_went_in(book: Book) -> None:
    save_programme(book, programme())
    assert get_programme(book, "pale ale two stand") == programme()


def test_the_legs_come_back_in_order(book: Book) -> None:
    """The order is the programme, so a set would be a different programme."""
    save_programme(book, programme())
    kinds = [leg.kind for leg in get_programme(book, "pale ale two stand").legs]
    assert kinds == [LegKind.WET_STAND, LegKind.AIR_REST, LegKind.WET_STAND]


def test_a_programme_that_is_not_there_says_which_one(book: Book) -> None:
    with pytest.raises(NotFoundError, match="no steep programme"):
        get_programme(book, "nothing")


def test_writing_a_programme_twice_is_refused(book: Book) -> None:
    save_programme(book, programme())
    with pytest.raises(ConflictError):
        save_programme(book, programme())


def test_programmes_list_in_name_order_and_by_style(book: Book) -> None:
    save_programme(book, programme("b lager", MaltStyle.LAGER))
    save_programme(book, programme("a pale"))
    assert [item.name for item in list_programmes(book)] == ["a pale", "b lager"]
    only = list_programmes(book, MaltStyle.LAGER)
    assert [item.name for item in only] == ["b lager"]


def test_a_schedule_reads_back_the_way_it_went_in(book: Book) -> None:
    save_schedule(book, schedule())
    assert get_schedule(book, "pale ale four day") == schedule()


def test_the_turning_points_come_back_in_order(book: Book) -> None:
    save_schedule(book, schedule())
    assert get_schedule(book, "pale ale four day").turns_at == (200.0, 500.0, 800.0)


def test_a_schedule_with_no_turns_reads_back_with_none(book: Book) -> None:
    save_schedule(book, Schedule("hand turned", MaltStyle.DISTILLING, 1400.0))
    assert get_schedule(book, "hand turned").turns == 0


def test_a_schedule_that_is_not_there_says_which_one(book: Book) -> None:
    with pytest.raises(NotFoundError, match="no germination schedule"):
        get_schedule(book, "nothing")


def test_schedules_list_in_name_order_and_by_style(book: Book) -> None:
    save_schedule(book, schedule("b lager", MaltStyle.LAGER))
    save_schedule(book, schedule("a pale"))
    assert [item.name for item in list_schedules(book)] == ["a pale", "b lager"]
    assert [item.name for item in list_schedules(book, MaltStyle.LAGER)] == ["b lager"]


def test_a_curve_reads_back_the_way_it_went_in(book: Book) -> None:
    save_curve(book, curve())
    assert get_curve(book, "pale ale 18 hour") == curve()


def test_the_steps_come_back_in_phase_order(book: Book) -> None:
    save_curve(book, curve())
    phases = [step.phase for step in get_curve(book, "pale ale 18 hour").steps]
    assert phases == [KilnPhase.FREE_DRYING, KilnPhase.BREAK, KilnPhase.CURING]


def test_a_curve_that_is_not_there_says_which_one(book: Book) -> None:
    with pytest.raises(NotFoundError, match="no kiln curve"):
        get_curve(book, "nothing")


def test_curves_list_in_name_order_and_by_style(book: Book) -> None:
    save_curve(book, curve("b lager", MaltStyle.LAGER))
    save_curve(book, curve("a pale"))
    assert [item.name for item in list_curves(book)] == ["a pale", "b lager"]
    assert [item.name for item in list_curves(book, MaltStyle.LAGER)] == ["b lager"]


def test_a_style_with_all_three_recipes_can_be_run(book: Book) -> None:
    save_programme(book, programme())
    save_schedule(book, schedule())
    save_curve(book, curve())
    assert recipes_for(book, MaltStyle.PALE_ALE) == (1, 1, 1)


def test_a_style_missing_a_curve_shows_up_before_a_piece_is_cast(book: Book) -> None:
    """Two programmes and no curve is a gap, and it is a gap in advance."""
    save_programme(book, programme())
    save_schedule(book, schedule())
    assert recipes_for(book, MaltStyle.PALE_ALE) == (1, 1, 0)


def test_a_style_with_nothing_has_nothing(book: Book) -> None:
    assert recipes_for(book, MaltStyle.VIENNA) == (0, 0, 0)


def test_a_failed_recipe_leaves_no_header_behind(book: Book) -> None:
    """The header and its children go in together or not at all."""
    save_programme(book, programme())
    with pytest.raises(ConflictError):
        save_programme(book, programme())
    assert book.scalar("SELECT count(*) FROM programme_leg") == 3


def test_the_book_refuses_a_leg_of_no_time(book: Book) -> None:
    save_programme(book, programme())
    with pytest.raises(ConflictError):
        book.execute(
            "INSERT INTO programme_leg (programme, seq, kind, hours, celsius) "
            "VALUES ('pale ale two stand', 9, 'wet_stand', 0.0, 14.0)"
        )
