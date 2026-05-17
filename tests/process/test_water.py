"""Steep water: what went in, what the barley kept, and what went to drain."""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.process.water import (
    TYPICAL_HIGH,
    TYPICAL_LOW,
    WaterUse,
    expected_m3,
    water_taken_up,
)


def use(piece: str = "2025-118", **kwargs: object) -> WaterUse:
    fields: dict[str, object] = {
        "charge_tonnes": 45.0,
        "charge_moisture": 12.0,
        "steep_out_moisture": 45.0,
        "metered_m3": 150.0,
        "malt_tonnes": 37.9,
    }
    fields.update(kwargs)
    return WaterUse(piece=piece, **fields)  # type: ignore[arg-type]


def test_the_barley_keeps_what_it_took_up() -> None:
    """45 tonnes at 12 percent going to 45 is 72 tonnes, so it kept 27."""
    assert water_taken_up(45.0, 12.0, 45.0) == pytest.approx(27.0, rel=1e-3)


def test_a_wetter_steep_out_keeps_more() -> None:
    assert water_taken_up(45.0, 12.0, 46.0) > water_taken_up(45.0, 12.0, 44.0)


def test_a_steep_that_did_not_wet_the_barley_is_refused() -> None:
    with pytest.raises(ValidationError, match="no wetter"):
        water_taken_up(45.0, 45.0, 44.0)


def test_what_went_to_drain_is_what_was_not_kept() -> None:
    """The figure the effluent bill is on, and it is not the meter reading."""
    piece = use()
    assert piece.to_drain_m3 == pytest.approx(150.0 - piece.taken_up_m3)
    assert piece.to_drain_m3 < piece.metered_m3


def test_a_meter_reading_under_what_the_barley_kept_is_refused() -> None:
    with pytest.raises(ValidationError, match="more than went over it"):
        use(metered_m3=10.0)


def test_a_weight_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="weight of nothing"):
        use(malt_tonnes=0.0)


def test_a_negative_meter_reading_is_refused() -> None:
    with pytest.raises(ValidationError, match="meter reading"):
        use(metered_m3=-1.0)


def test_the_specific_figure_is_per_tonne_of_malt() -> None:
    assert use().specific_m3_per_tonne == pytest.approx(150.0 / 37.9)


def test_a_plant_with_air_rests_is_inside_the_band() -> None:
    tidy = use(metered_m3=150.0)
    assert TYPICAL_LOW <= tidy.specific_m3_per_tonne <= TYPICAL_HIGH
    assert not tidy.heavy


def test_a_plant_dumping_between_stands_is_over_the_band() -> None:
    """Over the band is not a fault, it is a bill."""
    assert use(metered_m3=300.0).heavy


def test_the_drain_share_is_most_of_it() -> None:
    assert 0.5 < use().drain_share < 1.0


def test_a_piece_whose_meter_read_nothing_has_no_drain_share() -> None:
    """Which only happens on a meter that was not read, and is still an answer."""
    nothing = WaterUse(
        piece="2025-118",
        charge_tonnes=45.0,
        charge_moisture=45.0 - 1e-9,
        steep_out_moisture=45.0,
        metered_m3=0.0,
        malt_tonnes=37.9,
    )
    assert nothing.drain_share == pytest.approx(0.0)


def test_a_use_prints_all_three_figures() -> None:
    assert "150.0m3" in str(use())
    assert "to drain" in str(use())
    assert "a tonne" in str(use())


def test_the_expected_figure_is_the_rate_times_the_malt() -> None:
    assert expected_m3(37.9) == pytest.approx(37.9 * TYPICAL_LOW)
    assert expected_m3(37.9, 4.5) == pytest.approx(37.9 * 4.5)


def test_a_piece_making_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="is not a piece"):
        expected_m3(0.0)


def test_a_rate_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="is not a rate"):
        expected_m3(37.9, 0.0)
