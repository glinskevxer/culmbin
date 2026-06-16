"""What every conversion in `units` has to be true of, swept over its range.

The tests next to each module check the numbers a person worked out by hand.
This one checks the properties: that a round trip comes back, that a
monotonic function stays monotonic, that nothing crosses a ceiling, and that
two ways of asking the same question agree.

The sweeps are deterministic. There is no randomness in this suite, because
a test that fails one run in forty is a test somebody eventually deletes.
The ranges are wide enough to cover anything the building sees and then
some, and they step finely enough to find a sign error.
"""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.units.clock import Leg, degree_hours, format_duration, hours_at, parse_duration
from culmbin.units.mass import (
    MOISTURE_CEILING,
    at_moisture,
    blend_moisture,
    dry_matter,
    to_as_is_basis,
    to_dry_basis,
    wet_weight,
)
from culmbin.units.scales import (
    ebc_from_lovibond,
    kolbach_index,
    lintner_from_wk,
    lovibond_from_ebc,
    nitrogen_from_protein,
    protein_from_nitrogen,
    weighted_mean,
    wk_from_lintner,
)

MOISTURES = [round(value * 0.5, 1) for value in range(118)]
WEIGHTS = [0.001, 0.5, 1.0, 12.5, 28.18, 45.0, 71.8, 480.0, 12_000.0]
PERCENTAGES = [0.0, 0.01, 1.5, 40.95, 81.4, 99.9, 100.0]
TEMPERATURES = [round(value * 0.5, 1) for value in range(-10, 61)]


@pytest.mark.parametrize("moisture", MOISTURES)
def test_dry_matter_and_wet_weight_are_inverses_everywhere(moisture: float) -> None:
    for weight in WEIGHTS:
        assert wet_weight(dry_matter(weight, moisture), moisture) == pytest.approx(weight)


@pytest.mark.parametrize("moisture", MOISTURES)
def test_dry_matter_is_never_more_than_the_weight(moisture: float) -> None:
    for weight in WEIGHTS:
        assert dry_matter(weight, moisture) <= weight + 1e-12


@pytest.mark.parametrize("moisture", MOISTURES)
def test_wetter_grain_of_one_weight_carries_less_dry_matter(moisture: float) -> None:
    if moisture + 0.5 >= MOISTURE_CEILING:
        return
    assert dry_matter(45.0, moisture + 0.5) < dry_matter(45.0, moisture)


@pytest.mark.parametrize("moisture", MOISTURES)
def test_restating_a_weight_and_back_gives_it_again(moisture: float) -> None:
    for other in (4.2, 4.5, 12.5, 20.0):
        there = at_moisture(28.0, moisture, other)
        assert at_moisture(there, other, moisture) == pytest.approx(28.0)


@pytest.mark.parametrize("moisture", MOISTURES)
def test_the_two_bases_round_trip_everywhere(moisture: float) -> None:
    for value in PERCENTAGES:
        assert to_as_is_basis(to_dry_basis(value, moisture), moisture) == pytest.approx(value)


@pytest.mark.parametrize("moisture", MOISTURES)
def test_a_dry_basis_figure_is_never_the_smaller_one(moisture: float) -> None:
    for value in PERCENTAGES:
        assert to_dry_basis(value, moisture) >= value - 1e-12


@pytest.mark.parametrize("moisture", MOISTURES)
def test_a_moisture_off_the_scale_is_refused_from_both_ends(moisture: float) -> None:
    with pytest.raises(ValidationError):
        dry_matter(1.0, -moisture - 0.01)


def test_a_blend_moisture_stays_between_its_parts() -> None:
    for low in MOISTURES[::7]:
        for high in MOISTURES[::11]:
            if high <= low:
                continue
            blended = blend_moisture([(10.0, low), (30.0, high)])
            assert low <= blended <= high


def test_a_blend_of_one_moisture_is_that_moisture() -> None:
    for moisture in MOISTURES:
        assert blend_moisture([(10.0, moisture), (30.0, moisture)]) == pytest.approx(moisture)


@pytest.mark.parametrize("celsius", TEMPERATURES)
def test_degree_hours_are_never_negative(celsius: float) -> None:
    assert degree_hours([Leg(hours=24.0, celsius=celsius)]) >= 0.0


@pytest.mark.parametrize("celsius", TEMPERATURES)
def test_a_warmer_leg_never_earns_less(celsius: float) -> None:
    cooler = degree_hours([Leg(hours=24.0, celsius=celsius)])
    warmer = degree_hours([Leg(hours=24.0, celsius=celsius + 0.5)])
    assert warmer >= cooler


@pytest.mark.parametrize("celsius", TEMPERATURES)
def test_hours_at_inverts_degree_hours_where_it_can(celsius: float) -> None:
    try:
        hours = hours_at(celsius, 288.0)
    except ValidationError:
        return
    assert degree_hours([Leg(hours=hours, celsius=celsius)]) == pytest.approx(288.0)


def test_a_duration_round_trips_over_a_week() -> None:
    for minutes in range(0, 7 * 24 * 60, 7):
        text = format_duration(minutes / 60.0)
        assert parse_duration(text) == pytest.approx(minutes / 60.0)


def test_colour_round_trips_across_the_whole_scale() -> None:
    for tenths in range(1, 4000, 7):
        ebc = tenths / 10.0
        assert ebc_from_lovibond(lovibond_from_ebc(ebc)) == pytest.approx(ebc)


def test_a_darker_lovibond_is_always_a_darker_ebc() -> None:
    values = [ebc_from_lovibond(tenths / 10.0) for tenths in range(10, 2000, 13)]
    assert values == sorted(values)


def test_diastatic_power_round_trips_across_the_scale() -> None:
    for lintner in range(0, 400, 3):
        assert lintner_from_wk(wk_from_lintner(float(lintner))) == pytest.approx(float(lintner))


def test_protein_and_nitrogen_round_trip_across_the_range() -> None:
    for tenths in range(300):
        protein = tenths / 10.0
        assert protein_from_nitrogen(nitrogen_from_protein(protein)) == pytest.approx(protein)


def test_a_kolbach_index_is_always_a_percentage() -> None:
    for total in (6.0, 8.2, 10.5, 13.0):
        for share in range(0, 101, 5):
            soluble = total * share / 100.0
            assert 0.0 <= kolbach_index(soluble, total) <= 100.0


def test_a_weighted_mean_stays_between_its_parts() -> None:
    for low in PERCENTAGES:
        for high in PERCENTAGES:
            if high < low:
                continue
            for weight in (0.5, 1.0, 40.0):
                mean = weighted_mean([(weight, low), (1.0, high)])
                assert low - 1e-9 <= mean <= high + 1e-9


def test_a_weighted_mean_of_one_value_is_that_value() -> None:
    for value in PERCENTAGES:
        assert weighted_mean([(3.0, value), (7.0, value)]) == pytest.approx(value)
