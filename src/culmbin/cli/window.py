"""The `--from` and `--to` every command that covers a stretch of days takes.

Five command modules had written these two options out by hand, and the
default was computed in each of them. Four of them agreed and the fifth
defaulted `--to` to a week on rather than to the day being worked as, which
is a reasonable thing for a loading diary to do and was not written down
anywhere.

So the decorator is here once, the default is here once, and the loading
diary asks for its week explicitly.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any, TypeVar

import click

from culmbin.cli.context import Context
from culmbin.units.season import Window

F = TypeVar("F", bound=Callable[..., Any])


def window_options(command: F) -> F:
    """Add `--from` and `--to` to a command."""
    dated = click.option(
        "--from",
        "opens",
        type=click.DateTime(formats=["%Y-%m-%d"]),
        default=None,
        help="the first day. Defaults to the first of the month.",
    )(command)
    return click.option(
        "--to",
        "closes",
        type=click.DateTime(formats=["%Y-%m-%d"]),
        default=None,
        help="the last day. Defaults to the day being worked as.",
    )(dated)


def window_for(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> Window:
    """The window a command covers: the month to date unless told otherwise.

    A bare command is the month to date, which is what somebody typing it in
    a hurry means.
    """
    end = context.on if closes is None else closes.date()
    start = end.replace(day=1) if opens is None else opens.date()
    return Window(start, end)


def week_from(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> Window:
    """A window that defaults to the week ahead rather than the month behind.

    The loading diary wants this and nothing else does, which is why it is a
    second function rather than an argument to the first.
    """
    start = context.on if opens is None else opens.date()
    end = start + dt.timedelta(days=6) if closes is None else closes.date()
    return Window(start, end)
