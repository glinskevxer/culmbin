"""The degree hour clock.

These are the numbers the germination schedules are written against, so the
arithmetic here is checked against hand worked cases rather than against
itself.
"""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.units.clock import (
    GROWTH_BASE_C,
    Leg,
    check_temperature,
    degree_hours,
    elapsed_hours,
    format_duration,
    hours_at,
    mean_temperature,
    parse_duration,
)


def test_a_leg_holds_what_it_was_given() -> None:
    leg = Leg(hours=18.0, celsius=15.5)
    assert leg.hours == 18.0
    assert leg.celsius == 15.5


def test_a_leg_is_frozen() -> None:
    leg = Leg(hours=18.0, celsius=15.5)
    with pytest.raises(AttributeError):
        leg.hours = 19.0  # type: ignore[misc]


def test_a_negative_leg_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative"):
        Leg(hours=-1.0, celsius=15.0)


def test_a_leg_off_the_probe_scale_is_refused() -> None:
    with pytest.raises(ValidationError):
        Leg(hours=1.0, celsius=200.0)
    with pytest.raises(ValidationError):
        Leg(hours=1.0, celsius=-40.0)


def test_a_zero_hour_leg_is_legal() -> None:
    """A schedule can carry a step a particular piece skipped."""
    assert degree_hours([Leg(hours=0.0, celsius=16.0)]) == 0.0


def test_degree_hours_counts_above_the_base() -> None:
    """24 hours at 16 is 24 times 12, which is 288."""
    assert degree_hours([Leg(hours=24.0, celsius=16.0)]) == pytest.approx(288.0)


def test_degree_hours_adds_legs_up() -> None:
    legs = [Leg(hours=12.0, celsius=18.0), Leg(hours=12.0, celsius=14.0)]
    assert degree_hours(legs) == pytest.approx(12 * 14.0 + 12 * 10.0)


def test_a_cold_leg_contributes_nothing_rather_than_a_negative() -> None:
    warm = [Leg(hours=24.0, celsius=16.0)]
    with_a_cold_night = [*warm, Leg(hours=8.0, celsius=1.0)]
    assert degree_hours(with_a_cold_night) == degree_hours(warm)


def test_a_leg_exactly_at_the_base_contributes_nothing() -> None:
    assert degree_hours([Leg(hours=40.0, celsius=GROWTH_BASE_C)]) == 0.0


def test_degree_hours_of_nothing_is_nothing() -> None:
    assert degree_hours([]) == 0.0


def test_a_different_base_restates_the_clock() -> None:
    legs = [Leg(hours=10.0, celsius=14.0)]
    assert degree_hours(legs, base_c=0.0) == pytest.approx(140.0)
    assert degree_hours(legs, base_c=4.0) == pytest.approx(100.0)


def test_hours_at_inverts_degree_hours() -> None:
    hours = hours_at(16.0, 288.0)
    assert hours == pytest.approx(24.0)
    assert degree_hours([Leg(hours=hours, celsius=16.0)]) == pytest.approx(288.0)


def test_a_box_at_the_base_never_gets_there() -> None:
    with pytest.raises(ValidationError, match="never gets there"):
        hours_at(GROWTH_BASE_C, 100.0)


def test_a_negative_target_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative"):
        hours_at(16.0, -1.0)


def test_mean_temperature_is_time_weighted() -> None:
    """Six hours at 16 and eighteen at 14 is 14.5, not 15."""
    legs = [Leg(hours=6.0, celsius=16.0), Leg(hours=18.0, celsius=14.0)]
    assert mean_temperature(legs) == pytest.approx(14.5)


def test_mean_temperature_of_no_time_is_refused() -> None:
    with pytest.raises(ValidationError, match="no time passed"):
        mean_temperature([Leg(hours=0.0, celsius=16.0)])


def test_elapsed_hours_ignores_temperature() -> None:
    legs = [Leg(hours=6.0, celsius=1.0), Leg(hours=18.0, celsius=14.0)]
    assert elapsed_hours(legs) == pytest.approx(24.0)


@pytest.mark.parametrize(
    ("text", "hours"),
    [("18h30", 18.5), ("6h", 6.0), ("45m", 0.75), ("0h00", 0.0), (" 12h15 ", 12.25)],
)
def test_a_duration_reads_the_way_the_board_is_written(text: str, hours: float) -> None:
    assert parse_duration(text) == pytest.approx(hours)


@pytest.mark.parametrize("text", ["", "18", "18:30", "1h60m", "-6h", "eighteen", "18h30s"])
def test_a_duration_that_is_not_one_is_refused(text: str) -> None:
    with pytest.raises(ValidationError, match="not a duration"):
        parse_duration(text)


@pytest.mark.parametrize(("hours", "text"), [(18.5, "18h30"), (0.75, "0h45"), (0.0, "0h00")])
def test_a_duration_writes_back_the_way_it_was_read(hours: float, text: str) -> None:
    assert format_duration(hours) == text


def test_a_duration_round_trips() -> None:
    for text in ("18h30", "6h00", "0h45", "72h15"):
        assert format_duration(parse_duration(text)) == text


def test_formatting_a_negative_duration_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative"):
        format_duration(-1.0)


def test_check_temperature_returns_what_it_was_given() -> None:
    assert check_temperature(15.5) == 15.5


def test_check_temperature_names_the_field() -> None:
    with pytest.raises(ValidationError, match="kiln air"):
        check_temperature(500.0, field="kiln air")
