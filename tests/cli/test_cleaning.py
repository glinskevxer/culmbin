"""The cleaning commands."""

from __future__ import annotations

from tests.cli.conftest import Invoke


def plant(invoke: Invoke) -> None:
    invoke("party", "add", "DKEHOE", "D Kehoe", "--role", "haulier", on="2011-06-01")
    invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45", on="1998-04-01")


def test_a_cleaning_goes_in_and_comes_back(invoke: Invoke) -> None:
    plant(invoke)
    result = invoke(
        "clean", "record", "S1", "--by", "DKEHOE", "--note", "hot wash", on="2025-11-01"
    )
    assert result.exit_code == 0
    assert "cleaned on 2025-11-01" in result.output
    assert "hot wash" in invoke("clean", "show", "S1").output


def test_a_vessel_nobody_cleaned_says_so(invoke: Invoke) -> None:
    plant(invoke)
    assert "never been cleaned" in invoke("clean", "show", "S1").output


def test_setting_an_interval_starts_policing_it(invoke: Invoke) -> None:
    plant(invoke)
    result = invoke("clean", "interval", "S1", "--days", "30", "--pieces", "12")
    assert "now policed at 30 days or 12 pieces" in result.output


def test_an_unpoliced_vessel_is_on_the_page_as_one(invoke: Invoke) -> None:
    plant(invoke)
    assert "no interval set" in invoke("clean", "due").output


def test_a_policed_vessel_that_is_overdue_is_on_the_page(invoke: Invoke) -> None:
    plant(invoke)
    invoke("clean", "interval", "S1", "--days", "7", "--pieces", "4")
    text = invoke("clean", "due", on="2025-11-15").output
    assert "overdue" in text
    assert "S1" in text


def test_a_cleaning_by_somebody_not_in_the_register_is_refused(invoke: Invoke) -> None:
    plant(invoke)
    assert invoke("clean", "record", "S1", "--by", "NOBODY").exit_code != 0


def test_the_cleaning_report_is_the_same_page(invoke: Invoke) -> None:
    plant(invoke)
    assert "cleaning as at" in invoke("report", "cleaning").output
