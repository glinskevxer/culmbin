"""What a kiln run costs in gas, and why comparing two of them is hard."""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.process.energy import (
    GAS_MJ_PER_M3,
    MJ_PER_KWH,
    KilnEnergy,
    compare,
    gas_for,
    heat_from,
    heat_wanted,
    water_removed,
)


def run(piece: str = "2025-118", **kwargs: object) -> KilnEnergy:
    fields: dict[str, object] = {
        "green_tonnes": 72.0,
        "green_moisture": 44.0,
        "malt_tonnes": 42.1,
        "malt_moisture": 4.2,
        "gas_m3": 3160.0,
    }
    fields.update(kwargs)
    return KilnEnergy(piece=piece, **fields)  # type: ignore[arg-type]


def test_the_water_is_worked_through_the_dry_matter() -> None:
    """72 tonnes at 44 percent is 40.32 dry, which is 42.09 at 4.2."""
    assert water_removed(72.0, 44.0, 4.2) == pytest.approx(29_912.0, rel=1e-3)


def test_a_wetter_cast_carries_more_water() -> None:
    assert water_removed(72.0, 46.0, 4.2) > water_removed(72.0, 44.0, 4.2)


def test_malt_cannot_come_off_wetter_than_it_went_on() -> None:
    with pytest.raises(ValidationError, match="wetter than"):
        water_removed(72.0, 44.0, 50.0)


def test_the_heat_is_latent_and_sensible_together() -> None:
    assert heat_wanted(1000.0) == pytest.approx(2560.0)


def test_a_negative_amount_of_water_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot remove"):
        heat_wanted(-1.0)


def test_the_gas_expected_falls_as_efficiency_rises() -> None:
    assert gas_for(10_000.0, 0.7) < gas_for(10_000.0, 0.5)


def test_an_efficiency_that_is_not_one_is_refused() -> None:
    with pytest.raises(ValidationError, match="is not one"):
        gas_for(10_000.0, 1.4)
    with pytest.raises(ValidationError, match="is not one"):
        gas_for(10_000.0, 0.0)


def test_a_meter_reading_is_worth_its_calorific_value() -> None:
    assert heat_from(100.0) == pytest.approx(100.0 * GAS_MJ_PER_M3)


def test_a_negative_meter_reading_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot read"):
        heat_from(-1.0)


def test_a_run_needs_weights_and_a_meter() -> None:
    with pytest.raises(ValidationError, match="weight of nothing"):
        run(malt_tonnes=0.0)
    with pytest.raises(ValidationError, match="meter reading"):
        run(gas_m3=-1.0)


def test_a_run_that_came_off_wetter_is_refused() -> None:
    with pytest.raises(ValidationError, match="wetter than it went on"):
        run(malt_moisture=50.0)


def test_a_normal_run_is_in_the_efficiency_band() -> None:
    assert 0.5 <= run().efficiency <= 0.8
    assert not run().suspect


def test_a_run_that_burnt_far_too_much_is_suspect() -> None:
    assert run(gas_m3=7000.0).suspect


def test_a_run_that_says_it_burnt_almost_nothing_is_suspect() -> None:
    """Above four fifths, something is wrong with the meter."""
    assert run(gas_m3=2200.0).suspect


def test_a_run_that_burnt_nothing_has_no_efficiency() -> None:
    nothing_burnt = run(gas_m3=0.0)
    with pytest.raises(ValidationError, match="burnt nothing"):
        assert nothing_burnt.efficiency


def test_the_specific_energy_is_in_two_units() -> None:
    assert run().specific_energy_kwh_per_tonne == pytest.approx(
        run().specific_energy_mj_per_tonne / MJ_PER_KWH
    )


def test_a_wetter_cast_reports_a_worse_specific_energy() -> None:
    """The figure everybody quotes, and it moves without anything getting worse."""
    dry_cast = run(green_moisture=43.0, gas_m3=3000.0)
    wet_cast = run(green_moisture=46.0, gas_m3=3300.0)
    assert wet_cast.specific_energy_mj_per_tonne > dry_cast.specific_energy_mj_per_tonne


def test_efficiency_does_not_carry_the_cast_moisture_with_it() -> None:
    """Which is why it is the number worth comparing between runs."""
    dry_cast = run("A", green_moisture=43.0, gas_m3=3000.0)
    wet_cast = run("B", green_moisture=46.0, gas_m3=3300.0)
    assert abs(dry_cast.efficiency - wet_cast.efficiency) < 0.05


def test_the_comparison_says_when_more_gas_a_tonne_was_run_better() -> None:
    """The answer is nearly always the opposite of what the figures suggest."""
    tidy = run("A", green_moisture=42.0, gas_m3=2400.0)
    wet = run("B", green_moisture=48.0, gas_m3=2700.0)
    assert wet.efficiency > tidy.efficiency
    assert wet.specific_energy_mj_per_tonne > tidy.specific_energy_mj_per_tonne
    assert "despite using more gas a tonne" in compare(tidy, wet)


def test_the_comparison_is_plain_when_both_agree() -> None:
    better = run("A", gas_m3=3000.0)
    worse = run("B", gas_m3=3600.0)
    assert "used less gas a tonne" in compare(better, worse)


def test_two_runs_at_the_same_efficiency_are_said_to_be() -> None:
    assert "the same efficiency" in compare(run("A"), run("B"))
