"""The quality desk commands."""

from __future__ import annotations

from tests.cli.conftest import Invoke


def customer(invoke: Invoke) -> None:
    invoke("party", "add", "BRWY", "Sheldrake Brewing", "--role", "customer", on="2016-02-01")


def test_a_complaint_goes_in_and_comes_back(invoke: Invoke) -> None:
    customer(invoke)
    result = invoke(
        "complaint",
        "raise",
        "Q-1",
        "BRWY",
        "two EBC darker than the certificate",
        "--about",
        "colour",
        on="2026-01-14",
    )
    assert result.exit_code == 0
    assert "Q-1 BRWY colour (open)" in result.output


def test_a_complaint_with_no_shipment_says_it_cannot_be_walked(invoke: Invoke) -> None:
    customer(invoke)
    result = invoke(
        "complaint",
        "raise",
        "Q-1",
        "BRWY",
        "two EBC darker",
        "--about",
        "colour",
        on="2026-01-14",
    )
    assert "cannot be walked back yet" in result.output


def test_a_complaint_about_paperwork_says_nothing_about_walking(invoke: Invoke) -> None:
    customer(invoke)
    result = invoke(
        "complaint",
        "raise",
        "Q-2",
        "BRWY",
        "the certificate never arrived",
        "--about",
        "paperwork",
        on="2026-01-14",
    )
    assert "cannot be walked back" not in result.output


def test_a_complaint_shows_how_long_it_has_been_open(invoke: Invoke) -> None:
    customer(invoke)
    invoke(
        "complaint",
        "raise",
        "Q-1",
        "BRWY",
        "two EBC darker",
        "--about",
        "colour",
        on="2026-01-14",
    )
    result = invoke("complaint", "show", "Q-1", on="2026-01-20")
    assert "open      6 days" in result.output


def test_investigating_and_closing_a_complaint(invoke: Invoke) -> None:
    customer(invoke)
    invoke(
        "complaint",
        "raise",
        "Q-1",
        "BRWY",
        "two EBC darker",
        "--about",
        "colour",
        on="2026-01-14",
    )
    invoke("complaint", "investigate", "Q-1")
    result = invoke(
        "complaint",
        "close",
        "Q-1",
        "upheld",
        "--finding",
        "kiln ran hot on the cure",
        on="2026-01-28",
    )
    assert "closed as upheld after 14 days" in result.output
    assert "kiln ran hot" in invoke("complaint", "show", "Q-1").output


def test_closing_without_a_finding_is_not_possible(invoke: Invoke) -> None:
    customer(invoke)
    invoke(
        "complaint",
        "raise",
        "Q-1",
        "BRWY",
        "two EBC darker",
        "--about",
        "colour",
        on="2026-01-14",
    )
    assert invoke("complaint", "close", "Q-1", "upheld").exit_code == 2


def test_closing_twice_is_refused(invoke: Invoke) -> None:
    customer(invoke)
    invoke(
        "complaint",
        "raise",
        "Q-1",
        "BRWY",
        "two EBC darker",
        "--about",
        "colour",
        on="2026-01-14",
    )
    invoke("complaint", "close", "Q-1", "rejected", "--finding", "the retest agreed with us")
    result = invoke("complaint", "close", "Q-1", "upheld", "--finding", "changed our minds")
    assert result.exit_code != 0


def test_the_quality_page_prints(invoke: Invoke) -> None:
    customer(invoke)
    invoke(
        "complaint",
        "raise",
        "Q-1",
        "BRWY",
        "two EBC darker",
        "--about",
        "colour",
        on="2026-01-14",
    )
    result = invoke("complaint", "list", on="2026-01-31")
    assert "complaints 2026-01-01..2026-01-31" in result.output
    assert "Q-1" in result.output


def test_the_quality_report_is_the_same_page(invoke: Invoke) -> None:
    customer(invoke)
    assert "complaints" in invoke("report", "complaints", on="2026-01-31").output


def test_a_complaint_about_a_shipment_that_is_not_there_is_refused(invoke: Invoke) -> None:
    customer(invoke)
    invoke(
        "complaint",
        "raise",
        "Q-1",
        "BRWY",
        "two EBC darker",
        "--about",
        "colour",
        on="2026-01-14",
    )
    assert invoke("complaint", "attach", "Q-1", "S-9").exit_code != 0
