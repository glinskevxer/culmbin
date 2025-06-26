"""Blend plans and what they are predicted to assay.

The two tests that carry the design are the one where the wetter lot
contributes less extract, and the one where the blended Kolbach index is not
the mean of the two indices.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.blend.plan import Part, assess, common_codes, missing_codes, plan_of, predict
from culmbin.errors import StateError, ValidationError
from culmbin.model.enums import Basis, Conformance, MaltStyle, Material
from culmbin.model.lots import MaltLot
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.model.spec import Clause, specification
from culmbin.units.scales import kolbach_index, weighted_mean

TAKEN = dt.date(2025, 11, 12)


def lot(code: str, tonnes: float = 100.0, variety: str = "LAUR") -> MaltLot:
    return MaltLot(
        code=code,
        bin_code="B04",
        sealed=TAKEN,
        tonnes=tonnes,
        moisture=4.3,
        analysis=f"M-{code}",
        varieties=frozenset({variety}),
        crop_years=frozenset({2025}),
        style=MaltStyle.PALE_ALE,
    )


def malt(code: str, **values: float) -> Analysis:
    moisture = values.pop("moisture", 4.3)
    results = [Result("malt_moisture", moisture)]
    for name, value in values.items():
        basis = Basis.DRY if name in {"extract_fine", "total_protein", "soluble_protein"} else None
        results.append(Result(name, value, basis))
    return analysis_of(f"M-{code}", Material.MALT, TAKEN, results)


def part(code: str, tonnes: float = 50.0, **values: float) -> Part:
    return Part(lot=lot(code), tonnes=tonnes, analysis=malt(code, **values))


def test_a_plan_adds_its_tonnages() -> None:
    plan = plan_of("BL-1", [part("A", 60.0), part("B", 40.0)])
    assert plan.tonnes == pytest.approx(100.0)
    assert plan.share_of("A") == pytest.approx(0.6)


def test_a_plan_needs_a_code_and_parts() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        plan_of(" ", [part("A")])
    with pytest.raises(ValidationError, match="no parts"):
        plan_of("BL-1", [])


def test_a_plan_cannot_draw_from_one_lot_twice() -> None:
    with pytest.raises(ValidationError, match="one lot twice"):
        plan_of("BL-1", [part("A"), part("A")])


def test_a_part_cannot_draw_more_than_the_lot_holds() -> None:
    with pytest.raises(ValidationError, match="the plan draws"):
        Part(lot=lot("A", tonnes=20.0), tonnes=50.0, analysis=malt("A"))


def test_a_part_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="contributes"):
        Part(lot=lot("A"), tonnes=0.0, analysis=malt("A"))


def test_a_barley_analysis_is_not_a_malt_part() -> None:
    barley = analysis_of("B-1", Material.BARLEY, TAKEN, [Result("moisture", 12.4)])
    with pytest.raises(ValidationError, match="not a malt analysis"):
        Part(lot=lot("A"), tonnes=10.0, analysis=barley)


def test_a_lot_not_in_the_plan_has_no_share() -> None:
    plan = plan_of("BL-1", [part("A")])
    with pytest.raises(StateError, match="not in BL-1"):
        plan.share_of("Z")


def test_a_blend_of_one_variety_declares_it() -> None:
    plan = plan_of("BL-1", [part("A"), part("B")])
    assert plan.variety == "LAUR"


def test_a_blend_of_two_varieties_declares_nothing() -> None:
    second = Part(lot=lot("B", variety="DIAB"), tonnes=50.0, analysis=malt("B"))
    plan = plan_of("BL-1", [part("A"), second])
    assert plan.variety is None
    assert plan.varieties == frozenset({"LAUR", "DIAB"})


def test_moisture_blends_over_the_wet_weight() -> None:
    plan = plan_of("BL-1", [part("A", 10.0, moisture=4.0), part("B", 30.0, moisture=5.0)])
    assert predict(plan, "M-BL-1", TAKEN).moisture == pytest.approx(4.75)


def test_extract_blends_over_dry_matter_not_delivered_weight() -> None:
    """Equal tonnages, different moistures: the wetter one contributes less."""
    plan = plan_of(
        "BL-1",
        [
            part("A", 50.0, moisture=3.0, extract_fine=82.0),
            part("B", 50.0, moisture=6.0, extract_fine=80.0),
        ],
    )
    blended = predict(plan, "M-BL-1", TAKEN).value_on("extract_fine", Basis.DRY)
    assert blended > 81.0
    assert blended == pytest.approx(weighted_mean([(50.0 * 0.97, 82.0), (50.0 * 0.94, 80.0)]))


def test_colour_blends_over_the_weight_as_it_lies() -> None:
    plan = plan_of(
        "BL-1",
        [part("A", 30.0, moisture=3.0, colour=3.0), part("B", 10.0, moisture=6.0, colour=9.0)],
    )
    blended = predict(plan, "M-BL-1", TAKEN).value_on("colour", None)
    assert blended == pytest.approx(weighted_mean([(30.0, 3.0), (10.0, 9.0)]))


def test_the_two_weightings_give_different_answers() -> None:
    """Which is the whole reason the table in `blend.rules` exists."""
    plan = plan_of(
        "BL-1",
        [
            part("A", 30.0, moisture=3.0, colour=3.0, extract_fine=82.0),
            part("B", 10.0, moisture=6.0, colour=9.0, extract_fine=82.0),
        ],
    )
    on_as_is = weighted_mean([(30.0, 3.0), (10.0, 9.0)])
    on_dry = weighted_mean([(30.0 * 0.97, 3.0), (10.0 * 0.94, 9.0)])
    assert on_as_is != pytest.approx(on_dry)
    assert predict(plan, "M-BL-1", TAKEN).value_on("colour", None) == pytest.approx(on_as_is)


def test_the_kolbach_index_is_not_the_mean_of_the_indices() -> None:
    """A ratio of two means is not the mean of the ratios."""
    plan = plan_of(
        "BL-1",
        [
            part("A", 30.0, soluble_protein=4.3, total_protein=10.5, kolbach=41.0),
            part("B", 10.0, soluble_protein=3.4, total_protein=8.2, kolbach=41.5),
        ],
    )
    blended = predict(plan, "M-BL-1", TAKEN)
    by_index = weighted_mean(
        [
            (30.0 * 0.957, kolbach_index(4.3, 10.5)),
            (10.0 * 0.957, kolbach_index(3.4, 8.2)),
        ]
    )
    assert blended.value_on("kolbach", None) != pytest.approx(by_index, abs=0.01)
    assert blended.value_on("kolbach", None) == pytest.approx(
        kolbach_index(
            blended.value_on("soluble_protein", Basis.DRY),
            blended.value_on("total_protein", Basis.DRY),
        )
    )


def test_a_derived_result_needs_both_of_its_parts() -> None:
    plan = plan_of("BL-1", [part("A", 30.0, total_protein=10.5)])
    assert "kolbach" not in predict(plan, "M-BL-1", TAKEN)


def test_a_result_one_lot_is_missing_is_not_blended() -> None:
    plan = plan_of(
        "BL-1", [part("A", 30.0, colour=3.0, friability=84.0), part("B", 10.0, colour=9.0)]
    )
    predicted = predict(plan, "M-BL-1", TAKEN)
    assert "colour" in predicted
    assert "friability" not in predicted


def test_the_common_codes_are_what_every_part_has() -> None:
    plan = plan_of(
        "BL-1", [part("A", 30.0, colour=3.0, friability=84.0), part("B", 10.0, colour=9.0)]
    )
    assert common_codes(plan) == frozenset({"malt_moisture", "colour"})
    assert missing_codes(plan, frozenset({"friability", "colour"})) == frozenset({"friability"})


def test_an_uncertified_lot_stops_the_prediction() -> None:
    uncertified = MaltLot(
        code="C",
        bin_code="B04",
        sealed=TAKEN,
        tonnes=100.0,
        moisture=4.3,
        varieties=frozenset({"LAUR"}),
    )
    plan = plan_of("BL-1", [Part(lot=uncertified, tonnes=10.0, analysis=malt("C"))])
    with pytest.raises(StateError, match="cannot be predicted"):
        predict(plan, "M-BL-1", TAKEN)


def test_a_blend_that_meets_a_specification_passes() -> None:
    plan = plan_of(
        "BL-1",
        [
            part("A", 30.0, extract_fine=82.0, colour=3.4),
            part("B", 10.0, extract_fine=81.0, colour=3.8),
        ],
    )
    spec = specification(
        "lager 2025",
        Material.MALT,
        [Clause("extract_fine", basis=Basis.DRY, minimum=80.0), Clause("colour", maximum=5.0)],
    )
    assert assess(plan, spec, "M-BL-1", TAKEN).met


def test_a_blend_that_misses_a_clause_fails() -> None:
    plan = plan_of("BL-1", [part("A", 30.0, colour=6.4), part("B", 10.0, colour=7.0)])
    spec = specification("lager 2025", Material.MALT, [Clause("colour", maximum=5.0)])
    assert assess(plan, spec, "M-BL-1", TAKEN).conformance is Conformance.FAIL


def test_a_clause_no_lot_was_tested_for_is_untested() -> None:
    plan = plan_of("BL-1", [part("A", 30.0), part("B", 10.0)])
    spec = specification("lager 2025", Material.MALT, [Clause("friability", minimum=81.0)])
    assert assess(plan, spec, "M-BL-1", TAKEN).conformance is Conformance.UNTESTED


def test_two_pale_lots_cannot_be_blended_into_a_dark_one() -> None:
    """A blend stays between its parts, which is why blending fixes so little."""
    plan = plan_of("BL-1", [part("A", 30.0, colour=3.0), part("B", 10.0, colour=3.6)])
    blended = predict(plan, "M-BL-1", TAKEN).value_on("colour", None)
    assert 3.0 <= blended <= 3.6
