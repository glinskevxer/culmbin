"""Reading results, clauses and legs off a command line."""

from __future__ import annotations

import pytest

from culmbin.cli.values import (
    parse_clause,
    parse_draw,
    parse_leg,
    parse_result,
    parse_results,
    parse_step,
)
from culmbin.errors import NotFoundError, ValidationError
from culmbin.model.enums import Basis, KilnPhase, LegKind, Material


def test_a_result_takes_its_basis_off_the_table() -> None:
    """Typing the basis every time is how it eventually gets typed wrong."""
    assert parse_result("extract_fine=81.4").basis is Basis.DRY
    assert parse_result("colour=3.4").basis is None


def test_a_result_reads_its_value() -> None:
    assert parse_result("colour=3.4").value == pytest.approx(3.4)


def test_a_result_that_is_not_a_pair_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a result"):
        parse_result("colour")
    with pytest.raises(ValidationError, match="not a result"):
        parse_result("colour=3.4=5")


def test_a_value_that_is_not_a_number_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a number"):
        parse_result("colour=dark")


def test_an_analyte_that_is_not_one_is_refused() -> None:
    with pytest.raises(NotFoundError):
        parse_result("pH=5.4")


def test_results_have_to_be_about_one_material() -> None:
    with pytest.raises(ValidationError, match="malt determination"):
        parse_results(["moisture=12.5", "colour=3.4"], Material.BARLEY)


def test_results_of_one_material_come_back() -> None:
    results = parse_results(["moisture=12.5", "screenings=1.4"], Material.BARLEY)
    assert [item.code for item in results] == ["moisture", "screenings"]


def test_a_clause_with_a_ceiling() -> None:
    clause = parse_clause("colour<=4.5")
    assert clause.maximum == pytest.approx(4.5)
    assert clause.minimum is None


def test_a_clause_with_a_floor() -> None:
    clause = parse_clause("extract_fine>=80.5")
    assert clause.minimum == pytest.approx(80.5)
    assert clause.basis is Basis.DRY


def test_a_clause_with_both() -> None:
    clause = parse_clause("colour=2.5..4.5")
    assert clause.minimum == pytest.approx(2.5)
    assert clause.maximum == pytest.approx(4.5)


def test_a_clause_that_is_not_one_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a clause"):
        parse_clause("colour")


def test_a_clause_with_something_that_is_not_a_number_is_refused() -> None:
    with pytest.raises(ValidationError, match="where a number goes"):
        parse_clause("colour<=dark")


def test_a_wet_leg_and_an_air_rest() -> None:
    assert parse_leg("wet:8:14").kind is LegKind.WET_STAND
    assert parse_leg("air:16:16").kind is LegKind.AIR_REST
    assert parse_leg("wet:8:14").hours == pytest.approx(8.0)


def test_a_leg_that_is_not_one_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a steep leg"):
        parse_leg("warm:8:14")
    with pytest.raises(ValidationError, match="not a steep leg"):
        parse_leg("wet:8")


def test_the_three_kiln_steps() -> None:
    assert parse_step("dry:10:60").phase is KilnPhase.FREE_DRYING
    assert parse_step("break:4:70").phase is KilnPhase.BREAK
    assert parse_step("cure:4:85").phase is KilnPhase.CURING


def test_a_kiln_step_that_is_not_one_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a kiln step"):
        parse_step("hot:4:85")


def test_a_draw_is_a_lot_and_a_tonnage() -> None:
    assert parse_draw("L-2025-0412:40") == ("L-2025-0412", 40.0)


def test_a_draw_that_is_not_one_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a draw"):
        parse_draw("L-2025-0412")
