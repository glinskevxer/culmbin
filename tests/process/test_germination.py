"""The germination floor.

The rule these are mostly about is that everything is on the degree hour
clock, and the one that matters most is that a cold box gets fewer turns
rather than more.
"""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.model.enums import MaltStyle
from culmbin.process.germination import (
    MODIFICATION_CEILING,
    MODIFICATION_START,
    Schedule,
    accumulated,
    hours_to_cast,
    hours_to_next_turn,
    next_turn_at,
    predicted_modification,
    progress,
    ready,
    stalled,
    turns_due,
)
from culmbin.units.clock import GROWTH_BASE_C, Leg


def schedule(**kwargs: object) -> Schedule:
    fields: dict[str, object] = {
        "name": "pale ale four day",
        "style": MaltStyle.PALE_ALE,
        "target_degree_hours": 1200.0,
        "turns_at": (200.0, 500.0, 800.0),
    }
    fields.update(kwargs)
    return Schedule(**fields)  # type: ignore[arg-type]


def held(hours: float, celsius: float = 16.0) -> list[Leg]:
    """A box held at one temperature for a stretch."""
    return [Leg(hours=hours, celsius=celsius)]


def test_a_schedule_needs_a_name_and_a_target() -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        schedule(name=" ")
    with pytest.raises(ValidationError, match="degree hours"):
        schedule(target_degree_hours=0.0)


def test_turns_out_of_order_are_refused() -> None:
    with pytest.raises(ValidationError, match="out of order"):
        schedule(turns_at=(500.0, 200.0))


def test_the_same_turn_twice_is_refused() -> None:
    with pytest.raises(ValidationError, match="turns twice"):
        schedule(turns_at=(200.0, 200.0))


def test_a_turn_after_casting_off_is_refused() -> None:
    with pytest.raises(ValidationError, match="casts off at"):
        schedule(turns_at=(200.0, 1400.0))


def test_a_turn_at_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="turns at 0.0"):
        schedule(turns_at=(0.0,))


def test_a_schedule_with_no_turns_is_fine() -> None:
    """A traditional floor is turned by hand when the maltster says so."""
    assert schedule(turns_at=()).turns == 0


def test_degree_hours_are_counted_over_the_base() -> None:
    """24 hours at 16 is 24 times 12."""
    assert accumulated(schedule(), held(24.0, 16.0)) == pytest.approx(288.0)


def test_a_cold_night_earns_nothing_rather_than_a_negative() -> None:
    warm = held(24.0, 16.0)
    with_a_cold_night = [*warm, Leg(hours=8.0, celsius=GROWTH_BASE_C - 1.0)]
    assert accumulated(schedule(), with_a_cold_night) == accumulated(schedule(), warm)


def test_progress_is_a_percentage_of_the_target() -> None:
    legs = held(50.0, 16.0)
    assert progress(schedule(), legs) == pytest.approx(600.0 / 1200.0 * 100.0)


def test_a_piece_held_past_its_schedule_reads_over_a_hundred() -> None:
    """The kiln was full, and the number says so rather than stopping."""
    assert progress(schedule(), held(150.0, 16.0)) > 100.0


def test_a_piece_is_ready_when_it_has_earned_the_hours() -> None:
    assert not ready(schedule(), held(50.0, 16.0))
    assert ready(schedule(), held(100.0, 16.0))


def test_a_cold_box_gets_fewer_turns_over_the_same_days() -> None:
    """This is the whole reason the turns are on the degree hour clock."""
    warm = held(72.0, 17.0)
    cold = held(72.0, 11.0)
    assert turns_due(schedule(), warm) > turns_due(schedule(), cold)


def test_turns_come_due_as_the_clock_passes_them() -> None:
    assert turns_due(schedule(), held(10.0, 16.0)) == 0
    assert turns_due(schedule(), held(20.0, 16.0)) == 1
    assert turns_due(schedule(), held(45.0, 16.0)) == 2
    assert turns_due(schedule(), held(70.0, 16.0)) == 3


def test_a_turn_exactly_on_its_point_has_come_due() -> None:
    legs = [Leg(hours=200.0 / 12.0, celsius=16.0)]
    assert turns_due(schedule(), legs) == 1


def test_the_next_turn_is_the_first_one_not_taken() -> None:
    assert next_turn_at(schedule(), held(10.0, 16.0)) == pytest.approx(200.0)
    assert next_turn_at(schedule(), held(45.0, 16.0)) == pytest.approx(800.0)


def test_there_is_no_next_turn_when_they_are_all_done() -> None:
    assert next_turn_at(schedule(), held(90.0, 16.0)) is None
    assert hours_to_next_turn(schedule(), held(90.0, 16.0), 16.0) is None


def test_the_hours_to_the_next_turn_depend_on_the_box_temperature() -> None:
    """Somebody turning the attemperation down overnight changes the answer."""
    legs = held(10.0, 16.0)
    warm = hours_to_next_turn(schedule(), legs, 17.0)
    cool = hours_to_next_turn(schedule(), legs, 12.0)
    assert warm is not None
    assert cool is not None
    assert warm < cool


def test_the_hours_to_casting_off_run_down_to_nothing() -> None:
    assert hours_to_cast(schedule(), held(10.0, 16.0), 16.0) > 0.0
    assert hours_to_cast(schedule(), held(200.0, 16.0), 16.0) == 0.0


def test_a_kiln_slot_is_never_booked_for_a_negative() -> None:
    assert hours_to_cast(schedule(), held(300.0, 16.0), 16.0) >= 0.0


def test_modification_starts_where_green_malt_starts() -> None:
    assert predicted_modification(schedule(), []) == pytest.approx(MODIFICATION_START)


def test_modification_climbs_and_does_not_pass_the_ceiling() -> None:
    early = predicted_modification(schedule(), held(20.0, 16.0))
    late = predicted_modification(schedule(), held(100.0, 16.0))
    assert MODIFICATION_START < early < late < MODIFICATION_CEILING


def test_a_very_long_piece_approaches_the_ceiling() -> None:
    assert predicted_modification(schedule(), held(2000.0, 16.0)) == pytest.approx(
        MODIFICATION_CEILING, abs=0.1
    )


def test_a_schedule_takes_longer_in_a_cold_box() -> None:
    assert schedule().days_at(12.0) > schedule().days_at(18.0)


def test_a_four_day_schedule_is_about_four_days() -> None:
    assert schedule().days_at(16.0) == pytest.approx(1200.0 / 12.0 / 24.0)


def test_a_stalled_box_is_one_that_has_earned_nothing() -> None:
    legs = [Leg(hours=40.0, celsius=16.0), Leg(hours=14.0, celsius=3.0)]
    assert stalled(schedule(), legs)


def test_a_box_that_is_merely_cool_is_not_stalled() -> None:
    legs = [Leg(hours=40.0, celsius=16.0), Leg(hours=14.0, celsius=9.0)]
    assert not stalled(schedule(), legs)


def test_a_stall_shorter_than_the_window_is_not_one_yet() -> None:
    legs = [Leg(hours=40.0, celsius=16.0), Leg(hours=4.0, celsius=3.0)]
    assert not stalled(schedule(), legs)


def test_a_piece_with_no_readings_is_not_stalled() -> None:
    assert not stalled(schedule(), [])


def test_a_stall_window_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a stall"):
        stalled(schedule(), held(40.0), hours=0.0)
