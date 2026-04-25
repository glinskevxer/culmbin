"""The grower's statement."""

from __future__ import annotations

import datetime as dt

from culmbin.report.statement import statement_page
from culmbin.store.book import Book
from culmbin.units.season import Window
from tests.report.conftest import lorry

MONTH = Window(dt.date(2025, 9, 1), dt.date(2025, 9, 30))


def test_a_grower_with_nothing_delivered_says_so(week: Book) -> None:
    assert "nothing was delivered." in statement_page(week, "HOLB", MONTH)


def test_a_clean_load_is_on_the_statement_with_its_value(week: Book) -> None:
    lorry(week, "W-1")
    text = statement_page(week, "HOLB", MONTH)
    assert "W-1" in text
    assert "6551.85" in text
    assert "at 232.50" in text


def test_the_two_weights_are_next_to_each_other(week: Book) -> None:
    """The grower has his own ticket and will compare them first."""
    lorry(week, "W-1", moisture=15.0, screenings=3.4)
    text = statement_page(week, "HOLB", MONTH)
    assert "weighed" in text
    assert "settled" in text
    assert "Every difference between them is a line above." in text


def test_every_deduction_is_a_line_with_its_reason(week: Book) -> None:
    lorry(week, "W-1", moisture=15.0, screenings=3.4)
    text = statement_page(week, "HOLB", MONTH)
    assert "deductions" in text
    assert "screenings 3.4 over 2.0" in text
    assert "drying 2.5 points from 12.5" in text


def test_a_rejected_load_is_on_the_statement_and_worth_nothing(week: Book) -> None:
    """Leaving it off means the load he rings up about appears nowhere."""
    lorry(week, "W-1", germ_capacity=90.0)
    text = statement_page(week, "HOLB", MONTH)
    assert "W-1" in text
    assert "germination" in text
    assert "rejected        1" in text


def test_an_ungraded_load_is_marked_and_carries_no_value(week: Book) -> None:
    from culmbin.intake.desk import weigh_in
    from culmbin.model.intake import Delivery

    weigh_in(
        week,
        Delivery(
            ticket="W-9",
            purchase="P-HOLB",
            party="HOLB",
            arrived=dt.date(2025, 9, 18),
            gross_kg=43_820.0,
            tare_kg=15_640.0,
            harvested=dt.date(2025, 8, 14),
        ),
    )
    assert "not graded" in statement_page(week, "HOLB", MONTH)


def test_another_grower_is_left_off(week: Book) -> None:
    lorry(week, "W-1", party="HOLB")
    lorry(week, "W-2", party="WYKE")
    text = statement_page(week, "HOLB", MONTH)
    assert "W-1" in text
    assert "W-2" not in text


def test_the_statement_names_the_holding(week: Book) -> None:
    lorry(week, "W-1")
    assert "12/345" in statement_page(week, "HOLB", MONTH)


def test_a_load_outside_the_window_is_left_off(week: Book) -> None:
    lorry(week, "W-1")
    october = Window(dt.date(2025, 10, 1), dt.date(2025, 10, 31))
    assert "W-1" not in statement_page(week, "HOLB", october)


def test_the_page_ends_in_a_newline_and_has_no_trailing_space(week: Book) -> None:
    lorry(week, "W-1")
    text = statement_page(week, "HOLB", MONTH)
    assert text.endswith("\n")
    assert all(line == line.rstrip() for line in text.splitlines())
