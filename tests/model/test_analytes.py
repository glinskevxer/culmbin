"""The analyte table.

The table is the only place in the package that says what an analyte is, so
these tests are about the table being complete and self consistent rather
than about any one row.
"""

from __future__ import annotations

import pytest

from culmbin.errors import BasisError, NotFoundError, ValidationError
from culmbin.model.analytes import (
    ANALYTES,
    MOISTURE_OF,
    Analyte,
    analyte,
    analytes_for,
    convert,
    report,
)
from culmbin.model.enums import Basis, Material


def test_every_code_is_its_own_key() -> None:
    for code, item in ANALYTES.items():
        assert item.code == code


def test_every_analyte_has_a_label_and_a_unit() -> None:
    for item in ANALYTES.values():
        assert item.label
        assert item.unit


def test_no_two_analytes_share_a_label_within_a_material() -> None:
    """Two moistures is fine. Two moistures on malt would not be."""
    for material in Material:
        labels = [item.label for item in analytes_for(material)]
        assert len(labels) == len(set(labels))


def test_both_materials_are_measured() -> None:
    for material in Material:
        assert analytes_for(material)


def test_analytes_for_a_material_are_all_that_material() -> None:
    for material in Material:
        assert all(item.material is material for item in analytes_for(material))


def test_the_two_lists_together_are_the_whole_table() -> None:
    both = len(analytes_for(Material.BARLEY)) + len(analytes_for(Material.MALT))
    assert both == len(ANALYTES)


def test_every_material_has_a_moisture_and_it_is_in_the_table() -> None:
    for material in Material:
        code = MOISTURE_OF[material]
        assert analyte(code).material is material


def test_a_moisture_is_not_on_a_basis() -> None:
    """Moisture is not on a basis, it is the basis, so it carries none."""
    for code in MOISTURE_OF.values():
        assert analyte(code).basis is None


def test_nothing_without_a_basis_is_convertible() -> None:
    for item in ANALYTES.values():
        if item.basis is None:
            assert not item.convertible


def test_an_analyte_that_is_not_there_says_what_was_asked_for() -> None:
    with pytest.raises(NotFoundError, match="pH"):
        analyte("pH")


def test_a_convertible_analyte_cannot_be_declared_without_a_basis() -> None:
    with pytest.raises(ValidationError, match="cannot be converted"):
        Analyte("bogus", "bogus", Material.MALT, "%", None, 1, True)


def test_an_analyte_cannot_report_to_negative_places() -> None:
    with pytest.raises(ValidationError, match="places"):
        Analyte("bogus", "bogus", Material.MALT, "%", Basis.DRY, -1, False)


def test_extract_converts_between_the_bases() -> None:
    """81.4 on dry at 4.0 percent moisture is 78.14 as it lies."""
    as_is = convert("extract_fine", 81.4, Basis.DRY, Basis.AS_IS, 4.0)
    assert as_is == pytest.approx(78.144)


def test_a_conversion_to_the_same_basis_changes_nothing() -> None:
    assert convert("extract_fine", 81.4, Basis.DRY, Basis.DRY, 4.0) == 81.4


def test_a_conversion_round_trips() -> None:
    there = convert("total_protein", 10.5, Basis.DRY, Basis.AS_IS, 4.2)
    assert convert("total_protein", there, Basis.AS_IS, Basis.DRY, 4.2) == pytest.approx(10.5)


def test_colour_has_no_basis_to_convert_to() -> None:
    with pytest.raises(BasisError, match="not a percentage of a weight"):
        convert("colour", 5.5, Basis.DRY, Basis.AS_IS, 4.0)


def test_diastatic_power_has_a_basis_and_still_will_not_convert() -> None:
    """It is reported on dry malt, but a WK figure is not a fraction of a weight."""
    assert analyte("diastatic_power").basis is Basis.DRY
    with pytest.raises(BasisError):
        convert("diastatic_power", 250.0, Basis.DRY, Basis.AS_IS, 4.0)


def test_the_moisture_used_is_the_one_it_was_given() -> None:
    """Two moistures give two answers, which is why it is an argument."""
    at_four = convert("extract_fine", 81.4, Basis.DRY, Basis.AS_IS, 4.0)
    at_five = convert("extract_fine", 81.4, Basis.DRY, Basis.AS_IS, 5.0)
    assert at_four != pytest.approx(at_five)


def test_a_result_prints_to_the_places_the_table_says() -> None:
    assert report("extract_fine", 81.44) == "81.4"
    assert report("total_protein", 10.5) == "10.50"
    assert report("diastatic_power", 249.6) == "250"
    assert report("viscosity", 1.4712) == "1.471"


def test_printing_an_analyte_that_is_not_there_is_refused() -> None:
    with pytest.raises(NotFoundError):
        report("pH", 5.4)


def test_the_malt_side_carries_what_a_certificate_prints() -> None:
    codes = {item.code for item in analytes_for(Material.MALT)}
    assert {"extract_fine", "colour", "total_protein", "diastatic_power"} <= codes


def test_the_barley_side_carries_what_intake_grades_on() -> None:
    codes = {item.code for item in analytes_for(Material.BARLEY)}
    assert {"moisture", "nitrogen", "screenings", "germ_capacity"} <= codes
