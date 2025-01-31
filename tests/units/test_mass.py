"""Weight and moisture conversions.

The numbers in here are worked by hand in the docstrings where they are not
obvious, because a conversion test that only checks the function against
itself is not a test.
"""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.units.mass import (
    MOISTURE_CEILING,
    at_moisture,
    blend_moisture,
    dry_fraction,
    dry_matter,
    to_as_is_basis,
    to_dry_basis,
    wet_weight,
)


def test_dry_fraction_of_dry_grain_is_one() -> None:
    assert dry_fraction(0.0) == 1.0


def test_dry_fraction_of_twelve_percent() -> None:
    assert dry_fraction(12.0) == pytest.approx(0.88)


def test_dry_matter_takes_the_water_out() -> None:
    """A 45 tonne steep vessel at 12 percent holds 39.6 tonnes of barley."""
    assert dry_matter(45.0, 12.0) == pytest.approx(39.6)


def test_wet_weight_puts_it_back() -> None:
    assert wet_weight(39.6, 12.0) == pytest.approx(45.0)


def test_dry_matter_and_wet_weight_are_inverses() -> None:
    for moisture in (0.5, 4.2, 12.0, 20.0, 44.9):
        assert wet_weight(dry_matter(31.7, moisture), moisture) == pytest.approx(31.7)


def test_at_moisture_ships_fewer_tonnes_when_drier() -> None:
    """28 tonnes at 4.2 restated at 4.5 is 28.088, because the drier malt is worth more."""
    assert at_moisture(28.0, 4.2, 4.5) == pytest.approx(28.0879, rel=1e-4)


def test_at_moisture_is_the_identity_at_the_same_moisture() -> None:
    assert at_moisture(28.0, 4.5, 4.5) == pytest.approx(28.0)


def test_at_moisture_reverses() -> None:
    there = at_moisture(28.0, 4.2, 4.5)
    assert at_moisture(there, 4.5, 4.2) == pytest.approx(28.0)


def test_to_dry_basis_raises_the_number() -> None:
    """80.0 percent extract as it lies on 4.0 percent malt is 83.33 on dry."""
    assert to_dry_basis(80.0, 4.0) == pytest.approx(83.3333, rel=1e-5)


def test_to_as_is_basis_lowers_it_again() -> None:
    assert to_as_is_basis(83.3333, 4.0) == pytest.approx(80.0, rel=1e-5)


def test_the_two_bases_round_trip() -> None:
    for moisture in (2.0, 4.5, 6.0, 12.0):
        assert to_as_is_basis(to_dry_basis(81.4, moisture), moisture) == pytest.approx(81.4)


def test_the_bases_agree_on_bone_dry_grain() -> None:
    assert to_dry_basis(81.4, 0.0) == pytest.approx(81.4)


def test_blend_moisture_of_one_part_is_its_own() -> None:
    assert blend_moisture([(20.0, 4.3)]) == pytest.approx(4.3)


def test_blend_moisture_averages_over_wet_weight() -> None:
    """10 t at 4.0 and 30 t at 5.0 is 4.75, not 4.5."""
    assert blend_moisture([(10.0, 4.0), (30.0, 5.0)]) == pytest.approx(4.75)


def test_blend_moisture_ignores_a_zero_weight_part() -> None:
    assert blend_moisture([(10.0, 4.0), (0.0, 12.0)]) == pytest.approx(4.0)


@pytest.mark.parametrize("moisture", [-0.1, MOISTURE_CEILING, 61.0, 100.0])
def test_a_moisture_off_the_scale_is_refused(moisture: float) -> None:
    with pytest.raises(ValidationError):
        dry_fraction(moisture)


def test_a_fraction_passed_as_a_percentage_is_not_caught() -> None:
    """0.12 is a legal moisture, so the ceiling cannot save a caller from this."""
    assert dry_fraction(0.12) == pytest.approx(0.9988)


def test_a_negative_weight_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative"):
        dry_matter(-1.0, 12.0)


def test_a_negative_value_is_refused_on_both_bases() -> None:
    with pytest.raises(ValidationError):
        to_dry_basis(-1.0, 4.0)
    with pytest.raises(ValidationError):
        to_as_is_basis(-1.0, 4.0)


def test_an_empty_blend_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least one part"):
        blend_moisture([])


def test_a_blend_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="blend of nothing"):
        blend_moisture([(0.0, 4.0), (0.0, 5.0)])
