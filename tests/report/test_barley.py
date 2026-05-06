"""How the barley is grading, by grower and by month."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.report.barley import TRENDED, barley_page, trend_for
from culmbin.store.book import Book
from culmbin.units.season import Window
from tests.report.conftest import lorry

MONTH = Window(dt.date(2025, 9, 1), dt.date(2025, 9, 30))


def test_a_month_with_nothing_says_so(week: Book) -> None:
    assert "nobody delivered anything." in barley_page(week, MONTH)


def test_a_grower_who_delivered_is_on_the_page(week: Book) -> None:
    lorry(week, "W-1")
    text = barley_page(week, MONTH)
    assert "HOLB" in text
    assert "Holbeach Grange" in text


def test_every_trended_determination_is_a_column(week: Book) -> None:
    lorry(week, "W-1")
    text = barley_page(week, MONTH)
    for word in ("moisture", "nitrogen", "screenings", "germination"):
        assert word in text
    assert set(TRENDED) == {"moisture", "nitrogen", "screenings", "germ_capacity"}


def test_the_means_are_over_accepted_loads_only(week: Book) -> None:
    """A rejected load has no settled weight and would drag the mean with it."""
    lorry(week, "W-1", nitrogen=1.50)
    lorry(week, "W-2", nitrogen=1.95, germ_capacity=90.0)
    trend = trend_for(week, "HOLB", MONTH)
    assert trend.loads == 2
    assert trend.rejected == 1
    assert trend.means["nitrogen"] == pytest.approx(1.50)


def test_the_means_are_weighted_by_settled_tonnes(week: Book) -> None:
    """A twenty eight tonne lorry and a fourteen tonne one are not the same evidence."""
    lorry(week, "W-1", nitrogen=1.50)
    lorry(week, "W-2", nitrogen=1.90)
    trend = trend_for(week, "HOLB", MONTH)
    assert trend.means["nitrogen"] == pytest.approx(1.70)


def test_the_rejection_rate_is_the_last_column(week: Book) -> None:
    """Putting it first invites the opposite conclusion."""
    lorry(week, "W-1")
    text = barley_page(week, MONTH)
    heading_line = next(line for line in text.splitlines() if line.startswith("code"))
    assert heading_line.rstrip().endswith("rejected")


def test_a_grower_with_nothing_graded_is_left_off(week: Book) -> None:
    lorry(week, "W-1", party="HOLB")
    text = barley_page(week, MONTH)
    assert "WYKE" not in text


def test_a_grower_with_only_rejections_reports_a_hundred_percent(week: Book) -> None:
    lorry(week, "W-1", germ_capacity=90.0)
    trend = trend_for(week, "HOLB", MONTH)
    assert trend.rejection_rate == pytest.approx(100.0)
    assert trend.settled_tonnes == pytest.approx(0.0)


def test_a_grower_who_delivered_nothing_has_no_rate(week: Book) -> None:
    trend = trend_for(week, "WYKE", MONTH)
    assert trend.loads == 0
    assert trend.rejection_rate == pytest.approx(0.0)


def test_the_page_says_how_the_means_are_worked(week: Book) -> None:
    lorry(week, "W-1")
    assert "weighted by settled tonnes" in barley_page(week, MONTH)


def test_the_page_ends_in_a_newline_and_has_no_trailing_space(week: Book) -> None:
    lorry(week, "W-1")
    text = barley_page(week, MONTH)
    assert text.endswith("\n")
    assert all(line == line.rstrip() for line in text.splitlines())
