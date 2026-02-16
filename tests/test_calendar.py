"""Nothing in the package depends on what day the suite is run.

Thirty runs on one afternoon cannot see a date-dependent rule. Every one of
them agrees with every other, and the one day of the year where the answer
is different is the day nobody ran the suite.

So this module sweeps the clock rather than the inputs. Every rule that
takes a day is asked on a year of days, across three crop years and both
sides of every boundary the package has: the crop year opening in July, the
contract year opening in October, and the six weeks of dormancy after a
harvest.

It is slow by the standards of a unit test and it is the only place in the
suite that is.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.model.enums import Basis, Material, RejectionReason, ShipmentState
from culmbin.model.sales import Shipment
from culmbin.model.spec import Clause, specification
from culmbin.units.season import (
    DORMANCY_WEEKS,
    Window,
    contract_year,
    contract_year_window,
    crop_year,
    crop_year_window,
    dormancy_clears,
    is_new_crop,
    month_window,
)
from tests.support.samples import barley_sample, malt_analysis

YEARS = (2024, 2025, 2026)


def every_day(year: int) -> list[dt.date]:
    """Every day of a calendar year."""
    day = dt.date(year, 1, 1)
    days = []
    while day.year == year:
        days.append(day)
        day += dt.timedelta(days=1)
    return days


@pytest.mark.parametrize("year", YEARS)
def test_every_day_of_a_year_falls_in_exactly_one_crop_year(year: int) -> None:
    for day in every_day(year):
        window = crop_year_window(crop_year(day))
        assert window.contains(day)


@pytest.mark.parametrize("year", YEARS)
def test_every_day_of_a_year_falls_in_exactly_one_contract_year(year: int) -> None:
    for day in every_day(year):
        window = contract_year_window(contract_year(day))
        assert window.contains(day)


@pytest.mark.parametrize("year", YEARS)
def test_the_two_years_differ_on_exactly_a_quarter(year: int) -> None:
    """July to September, every year, and never anywhere else."""
    apart = [day for day in every_day(year) if crop_year(day) != contract_year(day)]
    assert len(apart) == 92
    assert {day.month for day in apart} == {7, 8, 9}


@pytest.mark.parametrize("year", YEARS)
def test_every_month_window_covers_its_month(year: int) -> None:
    for month in range(1, 13):
        window = month_window(year, month)
        assert window.start.month == month
        assert window.end.month == month
        assert (window.end + dt.timedelta(days=1)).month != month


@pytest.mark.parametrize("year", YEARS)
def test_dormancy_is_six_weeks_whatever_the_harvest_day(year: int) -> None:
    for day in every_day(year):
        assert (dormancy_clears(day) - day).days == DORMANCY_WEEKS * 7


@pytest.mark.parametrize("year", YEARS)
def test_new_crop_is_true_on_exactly_the_days_it_should_be(year: int) -> None:
    cut = dt.date(year, 8, 14)
    for day in every_day(year):
        wanted = crop_year(day) == crop_year(cut) and day < dormancy_clears(cut)
        assert is_new_crop(day, cut) is wanted


@pytest.mark.parametrize("year", YEARS)
def test_a_window_of_one_day_is_one_day_every_day_of_the_year(year: int) -> None:
    for day in every_day(year):
        assert Window(day, day).days == 1
        assert Window(day, day).contains(day)


def test_a_leap_day_is_a_day_like_any_other() -> None:
    day = dt.date(2024, 2, 29)
    assert Window(day, day).days == 1
    assert crop_year(day) == 2023
    assert month_window(2024, 2).end == day


@pytest.mark.parametrize("year", YEARS)
def test_the_screen_answers_the_same_on_every_old_crop_day(year: int) -> None:
    """Old crop is old crop, and the answer stops moving once dormancy clears."""
    from culmbin.intake.standard import Standard, screen

    cut = dt.date(year - 1, 8, 14)
    sample = barley_sample("B-1", dt.date(year, 1, 1), germ_energy=80.0)
    answers = {
        screen(Standard("s"), sample, cut, day)
        for day in every_day(year)
        if not is_new_crop(day, cut)
    }
    assert answers == {()}


@pytest.mark.parametrize("year", YEARS)
def test_the_screen_is_stricter_on_every_new_crop_day(year: int) -> None:
    from culmbin.intake.standard import Standard, screen

    cut = dt.date(year, 8, 14)
    sample = barley_sample("B-1", cut, germ_energy=80.0)
    days = [day for day in every_day(year) if is_new_crop(day, cut)]
    assert days
    for day in days:
        assert screen(Standard("s"), sample, cut, day) == (RejectionReason.GERMINATION,)


@pytest.mark.parametrize("year", YEARS)
def test_a_specification_assesses_the_same_whatever_day_it_is_asked(year: int) -> None:
    """An analysis carries its own date, so the day of the ask cannot matter."""
    spec = specification(
        "lager", Material.MALT, [Clause("extract_fine", basis=Basis.DRY, minimum=80.0)]
    )
    answers = set()
    for day in every_day(year)[::7]:
        analysis = malt_analysis("M-1", day, extract_fine=81.4)
        answers.add(spec.assess(analysis).conformance)
    assert len(answers) == 1


@pytest.mark.parametrize("year", YEARS)
def test_a_contract_tonne_does_not_move_with_the_calendar(year: int) -> None:
    for day in every_day(year)[::11]:
        shipment = Shipment(
            code="S-1",
            contract="C-1",
            lot="L-1",
            tonnes=28.0,
            moisture=4.2,
            despatched=day,
            state=ShipmentState.DESPATCHED,
        )
        assert shipment.contract_tonnes(4.5) == pytest.approx(28.0879, rel=1e-4)
