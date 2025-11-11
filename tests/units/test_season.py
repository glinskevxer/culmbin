"""The crop year, the contract year, dormancy and windows.

The dates in here are the ones the two years disagree on, because everywhere
else they agree and a test that only uses those proves nothing.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ValidationError
from culmbin.units.season import (
    DORMANCY_WEEKS,
    Window,
    contract_year,
    contract_year_opens,
    contract_year_window,
    crop_year,
    crop_year_opens,
    crop_year_window,
    dormancy_clears,
    is_new_crop,
    month_window,
    parse_date,
)


def test_the_crop_year_opens_in_july() -> None:
    assert crop_year(dt.date(2025, 6, 30)) == 2024
    assert crop_year(dt.date(2025, 7, 1)) == 2025


def test_the_crop_year_contains_its_own_harvest() -> None:
    """Barley cut in August is that year's crop, which is the point of July."""
    assert crop_year(dt.date(2025, 8, 14)) == 2025


def test_the_contract_year_opens_in_october() -> None:
    assert contract_year(dt.date(2025, 9, 30)) == 2024
    assert contract_year(dt.date(2025, 10, 1)) == 2025


def test_the_two_years_disagree_from_july_to_september() -> None:
    """The quarter between them is the whole reason both exist."""
    for day in (dt.date(2025, 7, 1), dt.date(2025, 8, 14), dt.date(2025, 9, 30)):
        assert crop_year(day) == 2025
        assert contract_year(day) == 2024


def test_the_two_years_agree_the_rest_of_the_time() -> None:
    for day in (dt.date(2025, 11, 4), dt.date(2026, 3, 1), dt.date(2026, 6, 29)):
        assert crop_year(day) == contract_year(day)


def test_dormancy_is_six_weeks_from_the_combine() -> None:
    assert dormancy_clears(dt.date(2025, 8, 14)) == dt.date(2025, 9, 25)
    assert DORMANCY_WEEKS == 6


def test_barley_is_new_crop_inside_dormancy() -> None:
    cut = dt.date(2025, 8, 14)
    assert is_new_crop(dt.date(2025, 9, 1), cut)


def test_barley_stops_being_new_crop_when_dormancy_clears() -> None:
    cut = dt.date(2025, 8, 14)
    assert not is_new_crop(dormancy_clears(cut), cut)


def test_old_crop_is_not_new_crop_whatever_the_date() -> None:
    """June barley from last year's crop is old crop, and nothing changed it."""
    cut = dt.date(2024, 8, 20)
    assert not is_new_crop(dt.date(2025, 6, 1), cut)


def test_new_crop_needs_the_same_crop_year_as_well_as_the_clock() -> None:
    """A July delivery off last year's crop is inside nobody's dormancy."""
    cut = dt.date(2024, 8, 20)
    assert not is_new_crop(dt.date(2025, 7, 2), cut)


def test_a_window_counts_both_ends() -> None:
    assert Window(dt.date(2025, 3, 1), dt.date(2025, 3, 31)).days == 31


def test_a_one_day_window_is_one_day() -> None:
    day = dt.date(2025, 3, 14)
    assert Window(day, day).days == 1


def test_a_backwards_window_is_refused() -> None:
    with pytest.raises(ValidationError, match="ends"):
        Window(dt.date(2025, 3, 31), dt.date(2025, 3, 1))


def test_a_window_contains_both_of_its_ends() -> None:
    window = Window(dt.date(2025, 3, 1), dt.date(2025, 3, 31))
    assert window.contains(dt.date(2025, 3, 1))
    assert window.contains(dt.date(2025, 3, 31))
    assert not window.contains(dt.date(2025, 4, 1))


def test_windows_that_touch_at_one_day_overlap() -> None:
    first = Window(dt.date(2025, 3, 1), dt.date(2025, 3, 31))
    second = Window(dt.date(2025, 3, 31), dt.date(2025, 4, 30))
    assert first.overlaps(second)
    assert second.overlaps(first)


def test_windows_a_day_apart_do_not_overlap() -> None:
    first = Window(dt.date(2025, 3, 1), dt.date(2025, 3, 30))
    second = Window(dt.date(2025, 3, 31), dt.date(2025, 4, 30))
    assert not first.overlaps(second)


def test_clipping_gives_the_shared_days() -> None:
    first = Window(dt.date(2025, 3, 1), dt.date(2025, 4, 15))
    second = Window(dt.date(2025, 4, 1), dt.date(2025, 4, 30))
    assert first.clipped_to(second) == Window(dt.date(2025, 4, 1), dt.date(2025, 4, 15))


def test_clipping_windows_that_miss_gives_nothing() -> None:
    first = Window(dt.date(2025, 3, 1), dt.date(2025, 3, 15))
    second = Window(dt.date(2025, 4, 1), dt.date(2025, 4, 30))
    assert first.clipped_to(second) is None


def test_a_window_prints_as_a_span() -> None:
    assert str(Window(dt.date(2025, 3, 1), dt.date(2025, 3, 31))) == "2025-03-01..2025-03-31"


def test_a_month_window_covers_the_month() -> None:
    assert month_window(2025, 2) == Window(dt.date(2025, 2, 1), dt.date(2025, 2, 28))
    assert month_window(2024, 2).days == 29
    assert month_window(2025, 12) == Window(dt.date(2025, 12, 1), dt.date(2025, 12, 31))


def test_a_month_that_is_not_one_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a month"):
        month_window(2025, 13)


def test_a_year_opens_on_the_day_the_window_starts() -> None:
    assert crop_year_opens(2025) == dt.date(2025, 7, 1)
    assert contract_year_opens(2025) == dt.date(2025, 10, 1)


def test_the_crop_year_window_is_a_year() -> None:
    window = crop_year_window(2025)
    assert window.start == dt.date(2025, 7, 1)
    assert window.end == dt.date(2026, 6, 30)
    assert window.days == 365


def test_the_contract_year_window_is_a_year() -> None:
    window = contract_year_window(2025)
    assert window.start == dt.date(2025, 10, 1)
    assert window.end == dt.date(2026, 9, 30)


def test_every_day_of_a_crop_year_reports_that_crop_year() -> None:
    window = crop_year_window(2025)
    for day in (window.start, dt.date(2025, 8, 14), dt.date(2026, 1, 1), window.end):
        assert crop_year(day) == 2025


def test_a_date_reads_and_says_which_field_it_was() -> None:
    assert parse_date("2025-03-14") == dt.date(2025, 3, 14)
    with pytest.raises(ValidationError, match="delivery window"):
        parse_date("14/03/2025", field="delivery window")
