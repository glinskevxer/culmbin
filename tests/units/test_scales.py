"""The analytical scales.

The conversions are checked against the published tables at the points the
tables print, and against each other everywhere else.
"""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.units.scales import (
    blend_kolbach_index,
    ebc_from_lovibond,
    hot_water_extract,
    kolbach_index,
    lintner_from_wk,
    lovibond_from_ebc,
    nitrogen_from_protein,
    protein_from_nitrogen,
    weighted_mean,
    wk_from_lintner,
)


def test_pale_ale_malt_colour_in_ebc() -> None:
    """Around 2.6 Lovibond, which is a shade under 6 EBC."""
    assert ebc_from_lovibond(2.6) == pytest.approx(5.44, abs=0.01)


def test_colour_round_trips_through_lovibond() -> None:
    for ebc in (2.5, 5.5, 12.0, 40.0, 180.0):
        assert ebc_from_lovibond(lovibond_from_ebc(ebc)) == pytest.approx(ebc)


def test_colour_round_trips_through_ebc() -> None:
    for lovibond in (1.5, 2.6, 8.0, 60.0):
        assert lovibond_from_ebc(ebc_from_lovibond(lovibond)) == pytest.approx(lovibond)


def test_a_negative_colour_is_refused() -> None:
    with pytest.raises(ValidationError, match="colour"):
        ebc_from_lovibond(-1.0)
    with pytest.raises(ValidationError, match="colour"):
        lovibond_from_ebc(-1.0)


def test_diastatic_power_at_the_usual_ale_malt_figure() -> None:
    """55 Lintner is 176.5 WK."""
    assert wk_from_lintner(55.0) == pytest.approx(176.5)


def test_diastatic_power_round_trips() -> None:
    for lintner in (35.0, 55.0, 120.0):
        assert lintner_from_wk(wk_from_lintner(lintner)) == pytest.approx(lintner)


def test_a_small_negative_wk_is_still_a_reading() -> None:
    """The WK scale runs below zero, so a very weak malt is not a mistake."""
    assert lintner_from_wk(-9.0) == pytest.approx(2.0)


def test_a_wk_below_the_lintner_scale_is_refused() -> None:
    with pytest.raises(ValidationError, match="bottom of the Lintner scale"):
        lintner_from_wk(-20.0)


def test_zero_wk_is_still_on_the_lintner_scale() -> None:
    """The offset means zero WK is 4.6 Lintner, which is weak but real."""
    assert lintner_from_wk(0.0) == pytest.approx(16.0 / 3.5)


def test_kolbach_is_a_percentage_of_total() -> None:
    """4.3 soluble on 10.5 total is 40.95, which is well modified."""
    assert kolbach_index(4.3, 10.5) == pytest.approx(40.952, rel=1e-4)


def test_kolbach_of_fully_soluble_protein_is_a_hundred() -> None:
    assert kolbach_index(10.5, 10.5) == pytest.approx(100.0)


def test_kolbach_refuses_soluble_above_total() -> None:
    with pytest.raises(ValidationError, match="above total protein"):
        kolbach_index(11.0, 10.5)


def test_kolbach_refuses_a_zero_total() -> None:
    with pytest.raises(ValidationError, match="not a divisor"):
        kolbach_index(0.0, 0.0)


def test_protein_and_nitrogen_round_trip() -> None:
    assert protein_from_nitrogen(1.68) == pytest.approx(10.5)
    assert nitrogen_from_protein(10.5) == pytest.approx(1.68)


def test_hot_water_extract_at_a_typical_certificate_figure() -> None:
    """80.5 percent as it lies is a little over 311 litre degrees per kilogram."""
    assert hot_water_extract(80.5) == pytest.approx(311.32, abs=0.01)


def test_hot_water_extract_of_nothing_is_nothing() -> None:
    assert hot_water_extract(0.0) == 0.0


def test_weighted_mean_of_one_part_is_its_own_value() -> None:
    assert weighted_mean([(30.0, 81.4)]) == pytest.approx(81.4)


def test_weighted_mean_leans_towards_the_heavier_part() -> None:
    """30 dry tonnes at 81.4 and 10 at 79.0 is 80.8."""
    assert weighted_mean([(30.0, 81.4), (10.0, 79.0)]) == pytest.approx(80.8)


def test_weighted_mean_over_no_weight_is_refused() -> None:
    with pytest.raises(ValidationError, match="no weight"):
        weighted_mean([(0.0, 81.4)])


def test_weighted_mean_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least one part"):
        weighted_mean([])


def test_a_negative_weight_is_refused_in_a_mean() -> None:
    with pytest.raises(ValidationError, match="weight"):
        weighted_mean([(-1.0, 81.4)])


def test_a_blend_of_one_part_keeps_its_index() -> None:
    assert blend_kolbach_index([(30.0, 4.3, 10.5)]) == pytest.approx(kolbach_index(4.3, 10.5))


def test_the_indices_agree_when_every_total_protein_is_the_same() -> None:
    """A ratio blends like an average only when the denominators match."""
    parts = [(30.0, 4.3, 10.5), (10.0, 3.9, 10.5)]
    by_index = weighted_mean([(w, kolbach_index(s, t)) for w, s, t in parts])
    assert blend_kolbach_index(parts) == pytest.approx(by_index)


def test_the_indices_disagree_when_the_total_proteins_differ() -> None:
    """This is the couple of points a specification argues about."""
    parts = [(30.0, 4.3, 10.5), (10.0, 3.4, 8.2)]
    by_index = weighted_mean([(w, kolbach_index(s, t)) for w, s, t in parts])
    blended = blend_kolbach_index(parts)
    assert blended != pytest.approx(by_index, abs=0.01)
    assert abs(blended - by_index) < 2.0


def test_a_kolbach_blend_stays_between_its_parts() -> None:
    parts = [(30.0, 4.3, 10.5), (10.0, 3.4, 8.2)]
    blended = blend_kolbach_index(parts)
    assert min(kolbach_index(s, t) for _, s, t in parts) <= blended
    assert blended <= max(kolbach_index(s, t) for _, s, t in parts)


def test_a_kolbach_blend_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least one part"):
        blend_kolbach_index([])
