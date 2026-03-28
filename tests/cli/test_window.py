"""The `--from` and `--to` every command that covers a stretch of days takes."""

from __future__ import annotations

import datetime as dt

import click

from culmbin.cli.context import Context
from culmbin.cli.window import week_from, window_for, window_options

TODAY = dt.date(2025, 11, 14)


def context() -> Context:
    return Context(path=":memory:", on=TODAY)


def moment(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)


def test_a_bare_command_covers_the_month_to_date() -> None:
    """Which is what somebody typing it in a hurry means."""
    window = window_for(context(), None, None)
    assert window.start == dt.date(2025, 11, 1)
    assert window.end == TODAY


def test_both_ends_can_be_given() -> None:
    window = window_for(context(), moment("2025-09-01"), moment("2025-09-30"))
    assert window.start == dt.date(2025, 9, 1)
    assert window.end == dt.date(2025, 9, 30)


def test_one_end_can_be_given() -> None:
    window = window_for(context(), None, moment("2025-09-30"))
    assert window.start == dt.date(2025, 9, 1)
    assert window.end == dt.date(2025, 9, 30)


def test_the_diary_looks_a_week_forward_instead() -> None:
    """The loading diary wants this and nothing else does."""
    week = week_from(context(), None, None)
    assert week.start == TODAY
    assert week.end == TODAY + dt.timedelta(days=6)
    assert week.days == 7


def test_the_diary_takes_both_ends_as_well() -> None:
    week = week_from(context(), moment("2025-11-17"), moment("2025-11-21"))
    assert week.start == dt.date(2025, 11, 17)
    assert week.end == dt.date(2025, 11, 21)


def test_the_decorator_adds_both_options() -> None:
    @window_options
    def command(opens: dt.datetime | None, closes: dt.datetime | None) -> None:
        """A command that covers a stretch of days."""

    wrapped = click.command()(command)
    names = {parameter.name for parameter in wrapped.params}
    assert {"opens", "closes"} <= names


def test_every_option_says_what_it_is_for() -> None:
    @window_options
    def command(opens: dt.datetime | None, closes: dt.datetime | None) -> None:
        """A command that covers a stretch of days."""

    wrapped = click.command()(command)
    for parameter in wrapped.params:
        if isinstance(parameter, click.Option):
            assert (parameter.help or "").strip()
