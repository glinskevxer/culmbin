"""The certificate of analysis.

The tests that carry weight are the ones about what the certificate must not
leave off: an untested clause, and the fact that a mixed lot has no variety.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import StateError
from culmbin.model.enums import Conformance
from culmbin.sales.certificate import build, render, write
from culmbin.store.book import Book
from tests.sales.conftest import a_lot

ISSUED = dt.date(2025, 11, 21)


def test_a_certificate_carries_the_lot_and_its_analysis(desk: Book) -> None:
    certificate = build(desk, "L-CLEAN")
    assert certificate.lot.code == "L-CLEAN"
    assert certificate.analysis.reference == "M-CLEAN"
    assert certificate.assessment is None


def test_a_lot_with_no_analysis_has_no_certificate(desk: Book) -> None:
    desk.execute("UPDATE malt_lot SET analysis = NULL WHERE code = 'L-CLEAN'")
    with pytest.raises(StateError, match="no certificate to write"):
        build(desk, "L-CLEAN")


def test_a_certificate_prints_the_lot_facts(desk: Book) -> None:
    text = write(desk, "L-CLEAN", ISSUED)
    assert "certificate of analysis L-CLEAN" in text
    assert "lot       L-CLEAN" in text
    assert "issued    2025-11-21" in text


def test_the_moisture_is_the_first_determination(desk: Book) -> None:
    """It is what all the others are relative to."""
    text = write(desk, "L-CLEAN", ISSUED)
    lines = [line for line in text.splitlines() if line.startswith("moisture")]
    body = text.splitlines()
    assert lines
    assert body.index(lines[0]) < body.index(
        next(line for line in body if line.startswith("fine grind extract"))
    )


def test_every_result_carries_its_unit(desk: Book) -> None:
    text = write(desk, "L-CLEAN", ISSUED)
    assert "EBC" in text
    assert "%" in text


def test_a_result_on_a_basis_says_which(desk: Book) -> None:
    text = write(desk, "L-CLEAN", ISSUED)
    assert "dry" in text


def test_a_result_with_no_basis_says_nothing_about_one(desk: Book) -> None:
    text = write(desk, "L-CLEAN", ISSUED)
    colour = next(line for line in text.splitlines() if line.startswith("colour"))
    assert "dry" not in colour
    assert "as is" not in colour


def test_a_clean_lot_prints_its_variety(desk: Book) -> None:
    assert "variety   LAUR" in write(desk, "L-CLEAN", ISSUED)


def test_a_mixed_lot_prints_its_varieties_and_no_variety_line(desk: Book) -> None:
    a_lot(desk, "L-MIXED", "B05", ("LAUR", "DIAB"), "M-MIXED")
    text = write(desk, "L-MIXED", ISSUED)
    assert "varieties  DIAB, LAUR" in text
    assert "\nvariety " not in text


def test_a_certificate_against_a_specification_shows_every_clause(desk: Book) -> None:
    text = write(desk, "L-CLEAN", ISSUED, specification="lager 2025")
    assert "against lager 2025" in text
    assert "fine grind extract" in text
    assert "colour" in text


def test_a_lot_that_meets_the_specification_says_so(desk: Book) -> None:
    text = write(desk, "L-CLEAN", ISSUED, specification="lager 2025")
    assert "this lot meets lager 2025" in text


def test_a_lot_outside_the_specification_is_marked(desk: Book) -> None:
    a_lot(desk, "L-DARK", "B05", ("LAUR",), "M-DARK", colour=6.2)
    text = write(desk, "L-DARK", ISSUED, specification="lager 2025")
    assert "OUT" in text
    assert "this lot OUT lager 2025" in text


def test_a_clause_nobody_ran_is_printed_as_not_tested(desk: Book) -> None:
    """A certificate with a line missing reads like a certificate that passed."""
    desk.execute("DELETE FROM result WHERE analysis = 'M-CLEAN' AND code = 'colour'")
    text = write(desk, "L-CLEAN", ISSUED, specification="lager 2025")
    assert "not tested" in text
    assert "colour" in text


def test_an_untested_certificate_does_not_claim_to_meet_the_specification(desk: Book) -> None:
    desk.execute("DELETE FROM result WHERE analysis = 'M-CLEAN' AND code = 'colour'")
    certificate = build(desk, "L-CLEAN", "lager 2025")
    assert certificate.conformance is Conformance.UNTESTED
    assert not certificate.in_specification


def test_a_certificate_with_no_specification_has_no_verdict(desk: Book) -> None:
    certificate = build(desk, "L-CLEAN")
    assert certificate.conformance is None
    assert not certificate.in_specification


def test_the_clause_requirement_is_printed_the_way_the_sheet_reads(desk: Book) -> None:
    text = write(desk, "L-CLEAN", ISSUED, specification="lager 2025")
    assert "colour 2.5 to 4.5 EBC" in text


def test_a_certificate_ends_in_a_newline(desk: Book) -> None:
    assert write(desk, "L-CLEAN", ISSUED).endswith("\n")


def test_no_line_of_a_certificate_has_trailing_space(desk: Book) -> None:
    text = write(desk, "L-CLEAN", ISSUED, specification="lager 2025")
    assert all(line == line.rstrip() for line in text.splitlines())


def test_rendering_twice_gives_the_same_page(desk: Book) -> None:
    """Nothing in here reads a clock of its own."""
    certificate = build(desk, "L-CLEAN", "lager 2025")
    assert render(certificate, ISSUED) == render(certificate, ISSUED)
