"""Kiln curves.

The test that matters is the one about two curves with the same curing
temperature coming off different colours, because that is the whole reason
the colour model takes moisture as well as heat.
"""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.model.enums import KilnPhase, MaltStyle
from culmbin.process.kiln import (
    BASE_COLOUR_EBC,
    EQUILIBRIUM_FLOOR,
    Curve,
    KilnStep,
    after_step,
    break_moisture,
    colour_from_step,
    curve_of,
    dry_down,
    equilibrium_moisture,
    meets_target,
    off_kiln_moisture,
    predicted_colour,
)

GREEN = 44.0


def drying(hours: float = 10.0, celsius: float = 60.0) -> KilnStep:
    return KilnStep(KilnPhase.FREE_DRYING, hours, celsius)


def breaking(hours: float = 4.0, celsius: float = 70.0) -> KilnStep:
    return KilnStep(KilnPhase.BREAK, hours, celsius)


def curing(hours: float = 4.0, celsius: float = 85.0) -> KilnStep:
    return KilnStep(KilnPhase.CURING, hours, celsius)


def curve(**kwargs: object) -> Curve:
    fields: dict[str, object] = {
        "name": "pale ale 18 hour",
        "style": MaltStyle.PALE_ALE,
        "steps": (drying(10.0, 60.0), breaking(4.0, 70.0), curing(4.0, 85.0)),
        "target_moisture": 4.2,
    }
    fields.update(kwargs)
    return Curve(**fields)  # type: ignore[arg-type]


def test_a_step_prints_the_way_the_sheet_reads() -> None:
    assert str(drying(10.0, 60.0)) == "free_drying 10h at 60C"


def test_a_step_of_no_time_is_not_a_step() -> None:
    with pytest.raises(ValidationError, match="is not a step"):
        drying(0.0)


def test_a_step_at_ambient_is_a_fan_and_not_a_kiln() -> None:
    with pytest.raises(ValidationError, match="it is a fan"):
        drying(10.0, 18.0)


def test_a_curve_needs_a_name_and_steps() -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        curve(name=" ")
    with pytest.raises(ValidationError, match="no steps"):
        curve(steps=())


def test_a_curve_starts_on_free_drying() -> None:
    with pytest.raises(ValidationError, match="not free drying"):
        curve(steps=(curing(4.0, 85.0),))


def test_a_curve_that_never_cures_is_refused() -> None:
    with pytest.raises(ValidationError, match="never cures"):
        curve(steps=(drying(10.0, 60.0),))


def test_a_curve_that_goes_back_a_phase_is_refused() -> None:
    steps = (drying(10.0, 60.0), curing(4.0, 85.0), breaking(2.0, 86.0))
    with pytest.raises(ValidationError, match="goes back to"):
        curve(steps=steps)


def test_a_curve_that_turns_the_kiln_down_is_refused() -> None:
    """That is an incident against a piece rather than a curve to run again."""
    steps = (drying(10.0, 70.0), breaking(4.0, 60.0), curing(4.0, 85.0))
    with pytest.raises(ValidationError, match="turns the kiln down"):
        curve(steps=steps)


def test_a_target_nobody_could_kiln_to_is_refused() -> None:
    with pytest.raises(ValidationError, match="percent off kiln"):
        curve(target_moisture=0.0)


def test_a_curve_adds_its_hours_up() -> None:
    assert curve().hours == pytest.approx(18.0)
    assert curve().hours_in(KilnPhase.CURING) == pytest.approx(4.0)
    assert curve().peak_c == pytest.approx(85.0)
    assert len(curve()) == 3


def test_hotter_air_settles_malt_lower() -> None:
    assert equilibrium_moisture(85.0) < equilibrium_moisture(60.0)


def test_the_equilibrium_has_a_floor() -> None:
    assert equilibrium_moisture(200.0) == pytest.approx(EQUILIBRIUM_FLOOR)


def test_a_step_takes_water_out() -> None:
    assert after_step(GREEN, drying()) < GREEN


def test_a_step_does_not_wet_malt_that_is_already_dry() -> None:
    dry = 2.0
    assert after_step(dry, drying(10.0, 60.0)) == pytest.approx(dry)


def test_nothing_dries_below_the_equilibrium_of_its_air() -> None:
    settled = equilibrium_moisture(60.0)
    assert after_step(GREEN, drying(400.0, 60.0)) >= settled - 1e-9


def test_the_dry_down_trace_has_one_entry_per_step() -> None:
    assert len(dry_down(curve(), GREEN)) == len(curve())


def test_the_dry_down_trace_never_goes_up() -> None:
    trace = dry_down(curve(), GREEN)
    assert list(trace) == sorted(trace, reverse=True)


def test_green_malt_off_the_scale_is_not_going_on_a_kiln() -> None:
    with pytest.raises(ValidationError, match="not going on a kiln"):
        dry_down(curve(), 70.0)


def test_an_eighteen_hour_curve_lands_near_its_target() -> None:
    assert meets_target(curve(), GREEN)


def test_a_curve_that_is_too_short_does_not_reach_the_target() -> None:
    short = curve(steps=(drying(2.0, 60.0), curing(1.0, 85.0)))
    assert not meets_target(short, GREEN)
    assert off_kiln_moisture(short, GREEN) > short.target_moisture


def test_a_cool_step_adds_no_colour() -> None:
    assert colour_from_step(20.0, 18.0, drying(10.0, 50.0)) == 0.0


def test_colour_needs_heat_and_water_and_time_together() -> None:
    hot_and_wet = colour_from_step(12.0, 10.0, curing(4.0, 85.0))
    hot_and_dry = colour_from_step(4.0, 3.8, curing(4.0, 85.0))
    assert hot_and_wet > hot_and_dry > 0.0


def test_a_longer_cure_is_darker() -> None:
    assert colour_from_step(10.0, 9.0, curing(8.0, 85.0)) > colour_from_step(
        10.0, 9.0, curing(4.0, 85.0)
    )


def test_a_curve_comes_off_darker_than_green_malt() -> None:
    assert predicted_colour(curve(), GREEN) > BASE_COLOUR_EBC


def long_drying() -> Curve:
    """Fourteen hours on cool air, so the bed is nearly dry before it gets hot."""
    return curve(steps=(drying(14.0, 54.0), breaking(4.0, 70.0), curing(4.0, 85.0)))


def short_drying() -> Curve:
    """Four hours on the same cool air, so it carries the water into the heat."""
    return curve(steps=(drying(4.0, 54.0), breaking(4.0, 70.0), curing(4.0, 85.0)))


def test_two_curves_curing_the_same_come_off_different_colours() -> None:
    """The one that dried down first is paler, and the curing step never knew."""
    assert long_drying().peak_c == short_drying().peak_c
    assert long_drying().hours_in(KilnPhase.CURING) == short_drying().hours_in(KilnPhase.CURING)
    assert predicted_colour(long_drying(), GREEN) < predicted_colour(short_drying(), GREEN)


def test_the_break_moisture_is_what_the_curve_carried_into_the_heat() -> None:
    assert break_moisture(long_drying(), GREEN) < break_moisture(short_drying(), GREEN)


def test_the_drying_air_itself_browns_once_it_is_over_the_base() -> None:
    """A long free drying step on hot air is not free, which is the other trap."""
    cool = curve(steps=(drying(14.0, 54.0), breaking(4.0, 70.0), curing(4.0, 85.0)))
    warm = curve(steps=(drying(14.0, 65.0), breaking(4.0, 70.0), curing(4.0, 85.0)))
    assert predicted_colour(warm, GREEN) > predicted_colour(cool, GREEN)


def test_a_curve_with_no_break_step_still_has_a_break_moisture() -> None:
    no_break = curve(steps=(drying(10.0, 60.0), curing(6.0, 85.0)))
    assert break_moisture(no_break, GREEN) == pytest.approx(dry_down(no_break, GREEN)[0])


def test_a_curve_that_is_all_free_drying_breaks_at_the_end() -> None:
    """It is refused as a curve, so this is worked on the steps directly."""
    moisture = GREEN
    for step in (drying(10.0, 60.0), drying(4.0, 60.0)):
        moisture = after_step(moisture, step)
    assert moisture < GREEN


def test_a_curve_builds_from_a_sequence() -> None:
    built = curve_of("lager", MaltStyle.LAGER, [drying(12.0, 55.0), curing(5.0, 80.0)], 4.5)
    assert built.style is MaltStyle.LAGER
    assert built.hours == pytest.approx(17.0)
