"""The quality standard and the rejection screen.

The screen is the gate everything else in intake sits behind, so most of
these are about a single threshold at a time. The two that are not are the
new crop rule and the order the reasons come back in.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ValidationError
from culmbin.intake.standard import SCREEN_CODES, Standard, missing_for_screen, screen
from culmbin.model.enums import Material, RejectionReason
from culmbin.model.results import Analysis, Result, analysis_of
from tests.support.samples import barley_sample

HARVESTED = dt.date(2025, 8, 14)
OLD_CROP_DAY = dt.date(2025, 11, 4)
NEW_CROP_DAY = dt.date(2025, 9, 1)


def sample(**overrides: float) -> Analysis:
    return barley_sample("B-2025-0918-03", OLD_CROP_DAY, **overrides)


def standard(**kwargs: object) -> Standard:
    fields: dict[str, object] = {"name": "malting 2025"}
    fields.update(kwargs)
    return Standard(**fields)  # type: ignore[arg-type]


def test_a_standard_needs_a_name() -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        standard(name=" ")


def test_a_standard_that_pays_past_its_rejection_is_refused() -> None:
    with pytest.raises(ValidationError, match="pays down to"):
        standard(moisture_base=21.0)


def test_a_nitrogen_band_the_wrong_way_round_is_refused() -> None:
    with pytest.raises(ValidationError, match="wrong way round"):
        standard(nitrogen_min=1.9, nitrogen_max=1.4)


def test_a_standard_that_deducts_past_its_rejection_is_refused() -> None:
    with pytest.raises(ValidationError, match="rejects at"):
        standard(nitrogen_max=2.2)


def test_a_standard_that_allows_more_than_it_rejects_at_is_refused() -> None:
    with pytest.raises(ValidationError, match="more screenings than"):
        standard(screenings_free=6.0)


def test_a_germination_floor_off_the_scale_is_refused() -> None:
    with pytest.raises(ValidationError, match="germination floor"):
        standard(germination_floor=120.0)
    with pytest.raises(ValidationError, match="energy floor"):
        standard(energy_floor=0.0)


def test_a_nitrogen_step_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="step of nothing"):
        standard(nitrogen_step=0.0)


def test_a_good_load_has_no_reasons() -> None:
    assert screen(standard(), sample(), HARVESTED, OLD_CROP_DAY) == ()


def test_low_germination_is_a_rejection_and_not_a_deduction() -> None:
    reasons = screen(standard(), sample(germ_capacity=94.0), HARVESTED, OLD_CROP_DAY)
    assert reasons == (RejectionReason.GERMINATION,)


def test_germination_exactly_on_the_floor_passes() -> None:
    assert screen(standard(), sample(germ_capacity=98.0), HARVESTED, OLD_CROP_DAY) == ()


def test_wet_barley_is_rejected() -> None:
    reasons = screen(standard(), sample(moisture=21.5), HARVESTED, OLD_CROP_DAY)
    assert reasons == (RejectionReason.MOISTURE,)


def test_moisture_exactly_on_the_threshold_passes() -> None:
    assert screen(standard(), sample(moisture=20.0), HARVESTED, OLD_CROP_DAY) == ()


def test_heavy_screenings_are_rejected() -> None:
    reasons = screen(standard(), sample(screenings=6.0), HARVESTED, OLD_CROP_DAY)
    assert reasons == (RejectionReason.SCREENINGS,)


def test_high_nitrogen_is_rejected() -> None:
    reasons = screen(standard(), sample(nitrogen=2.15), HARVESTED, OLD_CROP_DAY)
    assert reasons == (RejectionReason.NITROGEN,)


def test_nitrogen_in_the_deduction_band_is_not_a_rejection() -> None:
    """1.95 is over the band and under the rejection, which is the whole band."""
    assert screen(standard(), sample(nitrogen=1.95), HARVESTED, OLD_CROP_DAY) == ()


def test_admixture_is_rejected() -> None:
    reasons = screen(standard(), sample(admixture=3.0), HARVESTED, OLD_CROP_DAY)
    assert reasons == (RejectionReason.ADMIXTURE,)


def test_a_finding_rejects_a_load_that_grades_perfectly() -> None:
    reasons = screen(
        standard(),
        sample(),
        HARVESTED,
        OLD_CROP_DAY,
        findings=frozenset({RejectionReason.INSECT}),
    )
    assert reasons == (RejectionReason.INSECT,)


def test_reasons_come_back_in_the_order_of_the_enumeration() -> None:
    reasons = screen(
        standard(),
        sample(moisture=21.5, germ_capacity=90.0),
        HARVESTED,
        OLD_CROP_DAY,
        findings=frozenset({RejectionReason.ODOUR}),
    )
    assert reasons == (
        RejectionReason.GERMINATION,
        RejectionReason.MOISTURE,
        RejectionReason.ODOUR,
    )


def test_new_crop_is_screened_on_energy_as_well() -> None:
    """The same sample passes in November and fails in September."""
    weak = sample(germ_energy=88.0)
    assert screen(standard(), weak, HARVESTED, OLD_CROP_DAY) == ()
    assert screen(standard(), weak, HARVESTED, NEW_CROP_DAY) == (RejectionReason.GERMINATION,)


def test_old_crop_does_not_need_an_energy_result_at_all() -> None:
    results = [result for result in sample() if result.code != "germ_energy"]
    without = analysis_of("B-1", Material.BARLEY, OLD_CROP_DAY, results)
    assert screen(standard(), without, HARVESTED, OLD_CROP_DAY) == ()


def test_new_crop_without_an_energy_result_cannot_be_screened() -> None:
    results = [result for result in sample() if result.code != "germ_energy"]
    without = analysis_of("B-1", Material.BARLEY, NEW_CROP_DAY, results)
    with pytest.raises(ValidationError, match="germinative energy"):
        screen(standard(), without, HARVESTED, NEW_CROP_DAY)


def test_the_missing_list_says_what_a_new_crop_sample_still_needs() -> None:
    results = [result for result in sample() if result.code != "germ_energy"]
    without = analysis_of("B-1", Material.BARLEY, NEW_CROP_DAY, results)
    assert missing_for_screen(without, new_crop=True) == ("germ_energy",)
    assert missing_for_screen(without, new_crop=False) == ()


def test_a_sample_short_of_a_screen_result_cannot_be_screened() -> None:
    results = [result for result in sample() if result.code != "screenings"]
    without = analysis_of("B-1", Material.BARLEY, OLD_CROP_DAY, results)
    with pytest.raises(ValidationError, match="screenings"):
        screen(standard(), without, HARVESTED, OLD_CROP_DAY)


def test_the_screen_list_is_what_the_screen_reads() -> None:
    assert set(SCREEN_CODES) == {
        "moisture",
        "nitrogen",
        "screenings",
        "germ_capacity",
        "admixture",
    }


def test_screening_a_malt_analysis_is_refused() -> None:
    malt = analysis_of("M-1", Material.MALT, OLD_CROP_DAY, [Result("malt_moisture", 4.2)])
    with pytest.raises(ValidationError, match="screen is for barley"):
        screen(standard(), malt, HARVESTED, OLD_CROP_DAY)
