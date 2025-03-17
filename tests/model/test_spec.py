"""Specifications, clauses and what an assessment comes to.

Most of these are about the three way answer. A specification is met, not
met, or has not been looked at, and the third one is the one that gets lost.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import BasisError, ValidationError
from culmbin.model.enums import Basis, Conformance, Material
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.model.spec import (
    Assessment,
    Clause,
    ClauseOutcome,
    Specification,
    specification,
)

TAKEN = dt.date(2025, 11, 4)


def malt(*results: Result, moisture: float = 4.2) -> Analysis:
    return analysis_of(
        "M-2025-0412", Material.MALT, TAKEN, [Result("malt_moisture", moisture), *results]
    )


def lager_spec(*clauses: Clause) -> Specification:
    return specification("lager 2025", Material.MALT, list(clauses))


def test_a_clause_needs_a_bound() -> None:
    with pytest.raises(ValidationError, match="no floor and no ceiling"):
        Clause("colour")


def test_a_backwards_clause_is_refused() -> None:
    with pytest.raises(ValidationError, match="above ceiling"):
        Clause("colour", minimum=9.0, maximum=3.0)


def test_a_clause_on_a_basisless_analyte_must_not_name_a_basis() -> None:
    with pytest.raises(BasisError, match="cannot name one"):
        Clause("colour", basis=Basis.DRY, maximum=9.0)


def test_a_clause_on_an_analyte_with_a_basis_must_name_one() -> None:
    with pytest.raises(BasisError, match="names none"):
        Clause("extract_fine", minimum=80.0)


def test_both_bounds_are_inclusive() -> None:
    clause = Clause("colour", minimum=3.0, maximum=5.5)
    assert clause.holds(3.0)
    assert clause.holds(5.5)
    assert not clause.holds(2.9)
    assert not clause.holds(5.6)


def test_a_floor_only_clause_has_no_ceiling() -> None:
    clause = Clause("colour", minimum=3.0)
    assert clause.holds(3.0)
    assert clause.holds(900.0)
    assert not clause.holds(2.9)


def test_a_ceiling_only_clause_has_no_floor() -> None:
    clause = Clause("colour", maximum=5.5)
    assert clause.holds(0.0)
    assert not clause.holds(5.6)


def test_a_clause_prints_the_way_the_sheet_reads() -> None:
    assert str(Clause("colour", minimum=3.0, maximum=5.5)) == "colour 3 to 5.5 EBC"
    assert str(Clause("colour", maximum=5.5)) == "colour max 5.5 EBC"
    assert str(Clause("friability", minimum=81.0)) == "friability min 81 %"


def test_a_specification_needs_a_name_and_clauses() -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        specification(" ", Material.MALT, [Clause("colour", maximum=5.5)])
    with pytest.raises(ValidationError, match="no clauses"):
        specification("lager", Material.MALT, [])


def test_a_barley_clause_in_a_malt_specification_is_refused() -> None:
    with pytest.raises(ValidationError, match="barley clause"):
        specification("lager", Material.MALT, [Clause("screenings", maximum=2.0)])


def test_the_same_clause_twice_is_refused() -> None:
    with pytest.raises(ValidationError, match="twice"):
        lager_spec(Clause("colour", maximum=5.5), Clause("colour", maximum=6.0))


def test_a_met_clause_passes() -> None:
    spec = lager_spec(Clause("colour", minimum=3.0, maximum=5.5))
    assessment = spec.assess(malt(Result("colour", 4.1)))
    assert assessment.conformance is Conformance.PASS
    assert assessment.met


def test_a_broken_clause_fails_and_carries_the_value() -> None:
    spec = lager_spec(Clause("colour", maximum=5.5))
    assessment = spec.assess(malt(Result("colour", 6.2)))
    assert assessment.conformance is Conformance.FAIL
    assert len(assessment.failures) == 1
    assert assessment.failures[0].value == pytest.approx(6.2)


def test_a_clause_with_nothing_measured_is_untested_not_a_pass() -> None:
    spec = lager_spec(Clause("colour", maximum=5.5))
    assessment = spec.assess(malt())
    assert assessment.conformance is Conformance.UNTESTED
    assert not assessment.met
    assert assessment.untested[0].value is None


def test_a_failure_beats_an_untested_clause() -> None:
    spec = lager_spec(Clause("colour", maximum=5.5), Clause("friability", minimum=81.0))
    assessment = spec.assess(malt(Result("colour", 6.2)))
    assert assessment.conformance is Conformance.FAIL


def test_the_outcomes_keep_the_order_the_clauses_are_written_in() -> None:
    spec = lager_spec(
        Clause("friability", minimum=81.0),
        Clause("colour", maximum=5.5),
        Clause("fan", minimum=120.0),
    )
    assessment = spec.assess(malt(Result("colour", 4.1)))
    assert [outcome.clause.code for outcome in assessment] == [
        "friability",
        "colour",
        "fan",
    ]


def test_a_clause_is_assessed_on_the_basis_it_is_written_on() -> None:
    """The same malt meets one customer's clause and misses the other's."""
    analysis = malt(Result("extract_fine", 81.0, Basis.DRY), moisture=4.2)
    on_dry = lager_spec(Clause("extract_fine", basis=Basis.DRY, minimum=80.0))
    as_lies = lager_spec(Clause("extract_fine", basis=Basis.AS_IS, minimum=80.0))
    assert on_dry.assess(analysis).met
    assert not as_lies.assess(analysis).met


def test_the_moisture_of_the_analysis_decides_a_converted_clause() -> None:
    spec = lager_spec(Clause("extract_fine", basis=Basis.AS_IS, minimum=78.0))
    assert spec.assess(malt(Result("extract_fine", 81.4, Basis.DRY), moisture=4.0)).met
    assert not spec.assess(malt(Result("extract_fine", 81.4, Basis.DRY), moisture=5.0)).met


def test_assessing_the_wrong_material_is_refused() -> None:
    spec = lager_spec(Clause("colour", maximum=5.5))
    barley = analysis_of("B-1", Material.BARLEY, TAKEN, [Result("moisture", 12.4)])
    with pytest.raises(ValidationError, match="barley analysis"):
        spec.assess(barley)


def test_a_specification_counts_and_lists_its_codes() -> None:
    spec = lager_spec(Clause("colour", maximum=5.5), Clause("friability", minimum=81.0))
    assert len(spec) == 2
    assert spec.codes == frozenset({"colour", "friability"})
    assert [clause.code for clause in spec] == ["colour", "friability"]


def test_an_empty_assessment_is_a_pass() -> None:
    """Nothing to check is not a failure, and the caller decides what it means."""
    assert Assessment(()).conformance is Conformance.PASS


def test_an_outcome_knows_whether_it_failed() -> None:
    clause = Clause("colour", maximum=5.5)
    assert ClauseOutcome(clause, Conformance.FAIL, 6.2).failed
    assert not ClauseOutcome(clause, Conformance.UNTESTED, None).failed


def test_varieties_are_carried_but_not_assessed_here() -> None:
    """A variety is a property of the lot, not of the analysis, so it is elsewhere."""
    spec = specification(
        "distilling 2025",
        Material.MALT,
        [Clause("colour", maximum=4.0)],
        ["laureate", "diablo"],
    )
    assert spec.varieties == frozenset({"laureate", "diablo"})
