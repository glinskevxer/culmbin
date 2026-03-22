"""The report and trace commands.

These are thin, so the tests are about the window rule and about every page
being reachable, rather than about what is on any of them.
"""

from __future__ import annotations

import pytest

from tests.cli.conftest import Invoke

PAGES = [
    ("intake", "intake"),
    ("rejections", "rejections"),
    ("floor", "germination floor"),
    ("plant", "plant"),
    ("process", "in process"),
    ("balance", "malting loss and yield"),
    ("stock", "malt stock"),
    ("bins", "malt bins"),
    ("laboratory", "waiting on the laboratory"),
    ("contracts", "contract position"),
    ("calls", "call-offs"),
]


@pytest.mark.parametrize(("command", "heading"), PAGES)
def test_every_page_prints_on_an_empty_book(invoke: Invoke, command: str, heading: str) -> None:
    result = invoke("report", command)
    assert result.exit_code == 0
    assert heading in result.output


def test_the_window_defaults_to_the_month_to_date(invoke: Invoke) -> None:
    result = invoke("report", "intake", on="2025-11-14")
    assert "2025-11-01..2025-11-14" in result.output


def test_the_window_can_be_given_at_both_ends(invoke: Invoke) -> None:
    result = invoke("report", "intake", "--from", "2025-09-01", "--to", "2025-09-30")
    assert "2025-09-01..2025-09-30" in result.output


def test_the_window_can_be_given_at_one_end(invoke: Invoke) -> None:
    result = invoke("report", "intake", "--to", "2025-09-30")
    assert "2025-09-01..2025-09-30" in result.output


def test_the_floor_page_takes_a_temperature(invoke: Invoke) -> None:
    result = invoke("report", "floor", "--at", "18")
    assert "18.0C" in result.output


def test_a_grower_page_names_the_grower(invoke: Invoke) -> None:
    invoke("party", "add", "HOLB", "Holbeach", "--role", "grower", on="2011-06-01")
    result = invoke("report", "grower", "HOLB")
    assert "HOLB intake" in result.output


def test_a_trace_of_something_that_is_not_there_is_refused(invoke: Invoke) -> None:
    assert invoke("trace", "forward", "W-9").exit_code != 0
    assert invoke("trace", "back", "S-9").exit_code != 0


def test_every_report_is_in_the_help(invoke: Invoke) -> None:
    result = invoke("report", "--help")
    for command, _ in PAGES:
        assert command in result.output


def test_both_walks_are_in_the_help(invoke: Invoke) -> None:
    result = invoke("trace", "--help")
    assert "forward" in result.output
    assert "back" in result.output


def test_the_month_page_prints_on_an_empty_book(invoke: Invoke) -> None:
    result = invoke("report", "month", on="2025-11-30")
    assert result.exit_code == 0
    assert "month end 2025-11-01..2025-11-30" in result.output


def test_the_month_page_takes_a_window(invoke: Invoke) -> None:
    result = invoke("report", "month", "--from", "2025-09-01", "--to", "2025-09-30")
    assert "2025-09-01..2025-09-30" in result.output
