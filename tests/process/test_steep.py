"""Steep programmes and the uptake model.

The model is a fit and these tests treat it as one. What they hold is the
shape: monotonic, bounded by the ceiling, faster when warm, and slower on an
air rest than under water.
"""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.model.enums import LegKind, MaltStyle
from culmbin.process.steep import (
    UPTAKE_CEILING,
    Programme,
    SteepLeg,
    after_leg,
    hours_to_target,
    predicted_steep_out,
    programme_of,
    reaches_target,
    uptake,
    wet_rate,
)

BARLEY = 12.0


def wet(hours: float = 8.0, celsius: float = 14.0) -> SteepLeg:
    return SteepLeg(LegKind.WET_STAND, hours, celsius)


def air(hours: float = 16.0, celsius: float = 16.0) -> SteepLeg:
    return SteepLeg(LegKind.AIR_REST, hours, celsius)


def programme(**kwargs: object) -> Programme:
    fields: dict[str, object] = {
        "name": "pale ale two stand",
        "style": MaltStyle.PALE_ALE,
        "legs": (wet(8.0), air(16.0), wet(6.0), air(14.0), wet(4.0)),
        "target_moisture": 44.5,
    }
    fields.update(kwargs)
    return Programme(**fields)  # type: ignore[arg-type]


def test_a_leg_prints_the_way_the_sheet_reads() -> None:
    assert str(wet(8.0, 14.0)) == "wet 8h at 14C"
    assert str(air(16.0, 16.0)) == "air 16h at 16C"


def test_a_leg_of_no_time_is_not_a_leg() -> None:
    with pytest.raises(ValidationError, match="is not a leg"):
        SteepLeg(LegKind.WET_STAND, 0.0, 14.0)


def test_a_leg_at_an_impossible_temperature_is_refused() -> None:
    with pytest.raises(ValidationError, match="temperature"):
        SteepLeg(LegKind.WET_STAND, 8.0, 300.0)


def test_a_programme_needs_a_name_and_legs() -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        programme(name=" ")
    with pytest.raises(ValidationError, match="no legs"):
        programme(legs=())


def test_a_programme_starts_under_water() -> None:
    """An air rest with dry barley in it is not a step, it is waiting."""
    with pytest.raises(ValidationError, match="starts on an air rest"):
        programme(legs=(air(4.0), wet(8.0)))


def test_two_legs_of_a_kind_together_are_one_leg() -> None:
    with pytest.raises(ValidationError, match="which is one long one"):
        programme(legs=(wet(8.0), wet(6.0)))


def test_a_target_over_the_ceiling_is_refused() -> None:
    with pytest.raises(ValidationError, match="the ceiling is"):
        programme(target_moisture=52.0)


def test_a_programme_adds_its_hours_up() -> None:
    assert programme().wet_hours == pytest.approx(18.0)
    assert programme().air_hours == pytest.approx(30.0)
    assert programme().total_hours == pytest.approx(48.0)
    assert programme().stands == 3
    assert len(programme()) == 5


def test_a_wet_stand_takes_water_up() -> None:
    assert after_leg(BARLEY, wet(8.0)) > BARLEY


def test_an_air_rest_takes_a_little_up_and_much_less() -> None:
    """The corn is draining and the surface water is still going in."""
    wet_gain = after_leg(BARLEY, wet(8.0)) - BARLEY
    air_gain = after_leg(BARLEY, air(8.0)) - BARLEY
    assert 0.0 < air_gain < wet_gain


def test_nothing_passes_the_ceiling() -> None:
    long_steep = SteepLeg(LegKind.WET_STAND, 400.0, 20.0)
    assert after_leg(BARLEY, long_steep) <= UPTAKE_CEILING


def test_barley_already_at_the_ceiling_stays_there() -> None:
    assert after_leg(UPTAKE_CEILING, wet(8.0)) == pytest.approx(UPTAKE_CEILING)
    assert after_leg(UPTAKE_CEILING, air(8.0)) == pytest.approx(UPTAKE_CEILING)


def test_warm_water_is_faster_than_cold() -> None:
    assert after_leg(BARLEY, wet(8.0, 18.0)) > after_leg(BARLEY, wet(8.0, 10.0))
    assert wet_rate(18.0) > wet_rate(10.0)


def test_a_very_cold_steep_is_slow_and_not_backwards() -> None:
    assert wet_rate(-4.0) >= 0.0
    assert after_leg(BARLEY, wet(8.0, -4.0)) >= BARLEY


def test_the_uptake_trace_has_one_entry_per_leg() -> None:
    trace = uptake(programme(), BARLEY)
    assert len(trace) == len(programme())


def test_the_uptake_trace_never_goes_down() -> None:
    trace = uptake(programme(), BARLEY)
    assert list(trace) == sorted(trace)


def test_the_last_entry_is_the_predicted_steep_out() -> None:
    trace = uptake(programme(), BARLEY)
    assert predicted_steep_out(programme(), BARLEY) == pytest.approx(trace[-1])


def test_barley_off_the_scale_is_not_going_in_a_steep() -> None:
    with pytest.raises(ValidationError, match="not going into a steep"):
        uptake(programme(), 60.0)


def test_a_forty_eight_hour_programme_reaches_a_normal_target() -> None:
    assert reaches_target(programme(), BARLEY)


def test_a_short_programme_does_not_reach_it() -> None:
    short = programme(legs=(wet(4.0),))
    assert not reaches_target(short, BARLEY)


def test_wetter_barley_reaches_the_target_sooner() -> None:
    early = hours_to_target(programme(), 15.0)
    late = hours_to_target(programme(), 11.0)
    assert early is not None
    assert late is not None
    assert early < late


def test_a_programme_that_never_gets_there_says_nothing() -> None:
    assert hours_to_target(programme(legs=(wet(2.0),)), BARLEY) is None


def test_the_hour_it_reaches_the_target_is_inside_the_programme() -> None:
    hours = hours_to_target(programme(), BARLEY)
    assert hours is not None
    assert 0.0 < hours <= programme().total_hours


def test_a_programme_builds_from_a_sequence() -> None:
    built = programme_of("one stand", MaltStyle.LAGER, [wet(30.0)], 42.0)
    assert built.stands == 1
    assert built.style is MaltStyle.LAGER
