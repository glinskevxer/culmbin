"""Malting loss and yield.

The test that carries the point is the one where two pieces with identical
malting loss report different yields, because the barley came in wetter.
"""

from __future__ import annotations

import pytest

from culmbin.errors import ValidationError
from culmbin.process.losses import (
    CULM_FRACTION_OF_LOSS,
    TYPICAL_MALTING_LOSS,
    Balance,
    expected_culm_tonnes,
    expected_malt_tonnes,
    malting_loss,
    steep_out_tonnes,
    yield_percent,
)


def balance(**kwargs: object) -> Balance:
    fields: dict[str, object] = {
        "charge_tonnes": 45.0,
        "charge_moisture": 12.0,
        "steep_out_tonnes": 71.8,
        "steep_out_moisture": 44.8,
        "malt_tonnes": 37.9,
        "malt_moisture": 4.4,
        "culm_tonnes": 1.9,
    }
    fields.update(kwargs)
    return Balance(**fields)  # type: ignore[arg-type]


def test_malting_loss_is_the_dry_matter_that_went() -> None:
    """39.6 in and 36.2 out is 8.59 percent."""
    assert malting_loss(39.6, 36.2) == pytest.approx(8.586, rel=1e-3)


def test_a_piece_that_lost_nothing_has_no_loss() -> None:
    assert malting_loss(39.6, 39.6) == pytest.approx(0.0)


def test_a_piece_charged_with_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="is not a piece"):
        malting_loss(0.0, 0.0)


def test_a_negative_malt_weight_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot make"):
        malting_loss(39.6, -1.0)


def test_steep_out_is_the_same_barley_with_water_in_it() -> None:
    """39.6 dry tonnes at 44.8 percent is 71.7 wet tonnes."""
    assert steep_out_tonnes(45.0, 12.0, 44.8) == pytest.approx(71.74, rel=1e-3)


def test_a_wetter_steep_out_weighs_more() -> None:
    assert steep_out_tonnes(45.0, 12.0, 46.0) > steep_out_tonnes(45.0, 12.0, 43.0)


def test_the_expected_malt_carries_the_loss_and_the_moisture() -> None:
    """39.6 dry, less 8.5 percent, is 36.2 dry, which is 37.9 at 4.4 percent."""
    assert expected_malt_tonnes(45.0, 12.0, 4.4) == pytest.approx(37.91, rel=1e-3)


def test_a_bigger_loss_makes_less_malt() -> None:
    assert expected_malt_tonnes(45.0, 12.0, 4.4, 11.0) < expected_malt_tonnes(45.0, 12.0, 4.4, 8.0)


def test_wetter_malt_weighs_more_for_the_same_barley() -> None:
    assert expected_malt_tonnes(45.0, 12.0, 5.0) > expected_malt_tonnes(45.0, 12.0, 4.0)


def test_a_loss_that_is_not_a_percentage_is_refused() -> None:
    with pytest.raises(ValidationError, match="is not one"):
        expected_malt_tonnes(45.0, 12.0, 4.4, 120.0)


def test_the_culm_is_a_share_of_what_was_lost() -> None:
    lost = 45.0 * 0.88 * TYPICAL_MALTING_LOSS / 100.0
    assert expected_culm_tonnes(45.0, 12.0) == pytest.approx(lost * CULM_FRACTION_OF_LOSS)


def test_a_culm_share_that_is_not_a_share_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a share"):
        expected_culm_tonnes(45.0, 12.0, culm_share=1.4)


def test_yield_is_malt_out_over_barley_in() -> None:
    assert yield_percent(45.0, 37.9) == pytest.approx(84.22, rel=1e-3)


def test_a_yield_on_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a charge"):
        yield_percent(0.0, 10.0)


def test_two_pieces_with_the_same_loss_report_different_yields() -> None:
    """A wet autumn improves everybody's yield without anything being done better."""
    dry_barley = expected_malt_tonnes(45.0, 11.0, 4.4, 8.5)
    wet_barley = expected_malt_tonnes(45.0, 14.0, 4.4, 8.5)
    assert yield_percent(45.0, wet_barley) < yield_percent(45.0, dry_barley)
    assert malting_loss(45.0 * 0.89, dry_barley * 0.956) == pytest.approx(
        malting_loss(45.0 * 0.86, wet_barley * 0.956), abs=1e-9
    )


def test_a_balance_carries_both_of_its_dry_matters() -> None:
    assert balance().charge_dry_tonnes == pytest.approx(39.6)
    assert balance().malt_dry_tonnes == pytest.approx(37.9 * 0.956)


def test_a_balance_reports_a_normal_malting_loss() -> None:
    assert 6.0 < balance().malting_loss < 12.0


def test_a_balance_reports_a_normal_yield() -> None:
    assert 80.0 < balance().yield_percent < 88.0


def test_the_steep_discrepancy_is_nearly_nothing_on_a_good_piece() -> None:
    assert abs(balance().steep_discrepancy) < 2.0


def test_a_bad_weighbridge_shows_up_as_a_steep_discrepancy() -> None:
    """Four tonnes of dry matter appearing in a steep is a ticket, not a piece."""
    wrong = balance(steep_out_tonnes=79.0)
    assert wrong.steep_discrepancy > 2.0


def test_the_culm_share_is_near_the_expected_split() -> None:
    assert abs(balance().culm_share_of_loss - CULM_FRACTION_OF_LOSS) < 0.25


def test_a_piece_that_lost_nothing_has_no_culm_share() -> None:
    same_dry_matter = 39.6 / 0.956
    lossless = balance(malt_tonnes=same_dry_matter, malt_moisture=4.4, culm_tonnes=0.0)
    with pytest.raises(ValidationError, match="lost nothing"):
        assert lossless.culm_share_of_loss


def test_a_balance_with_a_weight_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="tonnes"):
        balance(malt_tonnes=0.0)


def test_a_negative_culm_weight_is_refused() -> None:
    with pytest.raises(ValidationError, match="culm weight"):
        balance(culm_tonnes=-1.0)


def test_a_steep_that_did_not_wet_the_barley_is_refused() -> None:
    with pytest.raises(ValidationError, match="no wetter"):
        balance(steep_out_moisture=11.0)


def test_malt_wetter_than_steep_out_is_refused() -> None:
    with pytest.raises(ValidationError, match="no drier"):
        balance(malt_moisture=45.0)


def test_a_piece_that_gained_dry_matter_is_refused() -> None:
    with pytest.raises(ValidationError, match="more barley in it than went in"):
        balance(malt_tonnes=44.0)
