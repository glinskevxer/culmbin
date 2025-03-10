"""Results and analyses.

The tests that matter here are the ones about basis, because everything else
is a container.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import BasisError, NotFoundError, ValidationError
from culmbin.model.enums import Basis, Material
from culmbin.model.results import Analysis, Result, analysis_of

TAKEN = dt.date(2025, 11, 4)


def malt_analysis(*results: Result, moisture: float = 4.2) -> Analysis:
    """A malt analysis with a moisture already in it, which they all need."""
    return analysis_of(
        "M-2025-0412",
        Material.MALT,
        TAKEN,
        [Result("malt_moisture", moisture), *results],
    )


def test_a_result_knows_its_label_and_unit() -> None:
    result = Result("colour", 5.5)
    assert result.label == "colour"
    assert result.unit == "EBC"


def test_a_result_on_a_basis_needs_one() -> None:
    with pytest.raises(BasisError, match="names none"):
        Result("extract_fine", 81.4)


def test_a_result_with_no_basis_must_not_carry_one() -> None:
    with pytest.raises(BasisError, match="has no basis"):
        Result("colour", 5.5, Basis.DRY)


def test_a_negative_result_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative"):
        Result("colour", -1.0)


def test_an_analysis_needs_a_reference() -> None:
    with pytest.raises(ValidationError, match="needs a reference"):
        analysis_of("  ", Material.MALT, TAKEN, [Result("malt_moisture", 4.2)])


def test_an_analysis_without_a_moisture_is_refused() -> None:
    with pytest.raises(ValidationError, match="without a moisture"):
        analysis_of("M-1", Material.MALT, TAKEN, [Result("colour", 5.5)])


def test_a_barley_result_in_a_malt_analysis_is_refused() -> None:
    with pytest.raises(ValidationError, match="barley result"):
        analysis_of(
            "M-1",
            Material.MALT,
            TAKEN,
            [Result("malt_moisture", 4.2), Result("screenings", 1.2)],
        )


def test_the_same_analyte_twice_is_refused() -> None:
    with pytest.raises(ValidationError, match="twice"):
        analysis_of(
            "M-1",
            Material.MALT,
            TAKEN,
            [Result("malt_moisture", 4.2), Result("colour", 5.5), Result("colour", 5.6)],
        )


def test_an_analysis_reports_its_own_moisture() -> None:
    assert malt_analysis(moisture=4.4).moisture == pytest.approx(4.4)


def test_a_barley_moisture_satisfies_a_barley_analysis() -> None:
    analysis = analysis_of("B-1", Material.BARLEY, TAKEN, [Result("moisture", 12.4)])
    assert analysis.moisture == pytest.approx(12.4)


def test_an_analysis_counts_and_iterates() -> None:
    analysis = malt_analysis(Result("colour", 5.5))
    assert len(analysis) == 2
    assert [result.code for result in analysis] == ["malt_moisture", "colour"]


def test_an_analysis_says_what_it_has() -> None:
    analysis = malt_analysis(Result("colour", 5.5))
    assert "colour" in analysis
    assert "friability" not in analysis
    assert 5.5 not in analysis


def test_a_missing_result_says_which_one() -> None:
    with pytest.raises(NotFoundError, match="friability"):
        malt_analysis()["friability"]


def test_get_treats_absence_as_an_answer() -> None:
    analysis = malt_analysis(Result("colour", 5.5))
    assert analysis.get("friability") is None
    got = analysis.get("colour")
    assert got is not None
    assert got.value == pytest.approx(5.5)


def test_a_value_on_its_own_basis_is_itself() -> None:
    analysis = malt_analysis(Result("extract_fine", 81.4, Basis.DRY))
    assert analysis.value_on("extract_fine", Basis.DRY) == pytest.approx(81.4)


def test_a_value_converts_on_the_analysis_moisture() -> None:
    """81.4 on dry at 4.2 percent is 77.98 as it lies, and 4.2 is this analysis's."""
    analysis = malt_analysis(Result("extract_fine", 81.4, Basis.DRY), moisture=4.2)
    assert analysis.value_on("extract_fine", Basis.AS_IS) == pytest.approx(77.981, rel=1e-4)


def test_two_analyses_of_the_same_malt_convert_differently() -> None:
    """This is the whole reason the analysis does the converting."""
    wet = malt_analysis(Result("extract_fine", 81.4, Basis.DRY), moisture=5.0)
    dry = malt_analysis(Result("extract_fine", 81.4, Basis.DRY), moisture=3.5)
    assert wet.value_on("extract_fine", Basis.AS_IS) < dry.value_on("extract_fine", Basis.AS_IS)


def test_asking_for_a_basis_on_something_with_none_is_refused() -> None:
    analysis = malt_analysis(Result("colour", 5.5))
    with pytest.raises(BasisError, match="cannot be reported"):
        analysis.value_on("colour", Basis.DRY)


def test_asking_for_no_basis_on_something_that_has_one_is_refused() -> None:
    analysis = malt_analysis(Result("extract_fine", 81.4, Basis.DRY))
    with pytest.raises(BasisError, match="cannot be reported"):
        analysis.value_on("extract_fine", None)


def test_a_basisless_value_comes_back_as_it_is() -> None:
    analysis = malt_analysis(Result("colour", 5.5))
    assert analysis.value_on("colour", None) == pytest.approx(5.5)


def test_adding_a_result_leaves_the_original_alone() -> None:
    first = malt_analysis()
    second = first.with_result(Result("colour", 5.5))
    assert len(first) == 1
    assert len(second) == 2
    assert second.reference == first.reference


def test_an_analysis_is_frozen() -> None:
    analysis = malt_analysis()
    with pytest.raises(AttributeError):
        analysis.reference = "M-2"  # type: ignore[misc]


def test_the_codes_are_what_is_in_it() -> None:
    analysis = malt_analysis(Result("colour", 5.5))
    assert analysis.codes == frozenset({"malt_moisture", "colour"})


def test_the_mapping_is_the_values_as_stored() -> None:
    analysis = malt_analysis(Result("extract_fine", 81.4, Basis.DRY))
    assert analysis.as_mapping() == {"malt_moisture": 4.2, "extract_fine": 81.4}
