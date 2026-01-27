"""Commands that print a page.

Every one of these is a thin wrapper over something in `report`, and that is
deliberate: the page is worked out somewhere that can be tested without a
console, and this layer only decides what the window is.

The window rule is the same everywhere. `--from` defaults to the first of
the month the book is being worked on and `--to` defaults to that day, so a
bare `report intake` is the month to date, which is what somebody typing it
in a hurry means.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any, TypeVar

import click

from culmbin.cli.context import Context, pass_context
from culmbin.report.floor import in_process_page, plant_page, shift_sheet
from culmbin.report.intake import day_sheet, grower_page, rejection_page
from culmbin.report.process import balance_page
from culmbin.report.quality import quality_page
from culmbin.report.sales import call_page, contract_page
from culmbin.report.stock import bin_page, laboratory_page, stock_page
from culmbin.report.walks import investigation_page, recall_page
from culmbin.report.yard import yard_page
from culmbin.units.season import Window

F = TypeVar("F", bound=Callable[..., Any])


def _window(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> Window:
    """The window a page covers: the month to date unless told otherwise."""
    end = context.on if closes is None else closes.date()
    start = end.replace(day=1) if opens is None else opens.date()
    return Window(start, end)


def _window_options(command: F) -> F:
    """Add `--from` and `--to` to a command, since five of them want them."""
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


@click.group()
def report() -> None:
    """The pages somebody actually reads."""


@report.command("intake")
@_window_options
@pass_context
def report_intake(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> None:
    """What came in, what is waiting, and what it settled at."""
    click.echo(day_sheet(context.book(), _window(context, opens, closes), context.on), nl=False)


@report.command("rejections")
@_window_options
@pass_context
def report_rejections(
    context: Context, opens: dt.datetime | None, closes: dt.datetime | None
) -> None:
    """Every load that went back, with the reason on each."""
    click.echo(rejection_page(context.book(), _window(context, opens, closes)), nl=False)


@report.command("grower")
@click.argument("party")
@_window_options
@pass_context
def report_grower(
    context: Context, party: str, opens: dt.datetime | None, closes: dt.datetime | None
) -> None:
    """Every load from one grower, for the statement."""
    click.echo(grower_page(context.book(), party, _window(context, opens, closes)), nl=False)


@report.command("floor")
@click.option(
    "--at",
    "celsius",
    type=float,
    default=16.0,
    show_default=True,
    help="the box temperature the clock is run at.",
)
@pass_context
def report_floor(context: Context, celsius: float) -> None:
    """The germination floor, worst first."""
    click.echo(shift_sheet(context.book(), at_celsius=celsius), nl=False)


@report.command("complaints")
@_window_options
@pass_context
def report_complaints(
    context: Context, opens: dt.datetime | None, closes: dt.datetime | None
) -> None:
    """Every complaint, with the ones nobody can walk back at the top."""
    click.echo(quality_page(context.book(), _window(context, opens, closes), context.on), nl=False)


@report.command("yard")
@pass_context
def report_yard(context: Context) -> None:
    """What is in the silos and what is still in the intake pit."""
    click.echo(yard_page(context.book()), nl=False)


@report.command("plant")
@pass_context
def report_plant(context: Context) -> None:
    """What is in every vessel, and what is free."""
    click.echo(plant_page(context.book()), nl=False)


@report.command("process")
@pass_context
def report_process(context: Context) -> None:
    """Every piece anywhere in the plant, by stage."""
    click.echo(in_process_page(context.book()), nl=False)


@report.command("balance")
@pass_context
def report_balance(context: Context) -> None:
    """Malting loss and yield for every finished piece."""
    click.echo(balance_page(context.book()), nl=False)


@report.command("stock")
@pass_context
def report_stock(context: Context) -> None:
    """Every lot, with what is free on it."""
    click.echo(stock_page(context.book()), nl=False)


@report.command("bins")
@pass_context
def report_bins(context: Context) -> None:
    """Every bin, what is in it, and whether it is mixed."""
    click.echo(bin_page(context.book()), nl=False)


@report.command("laboratory")
@pass_context
def report_laboratory(context: Context) -> None:
    """Every sealed lot with no certificate against it."""
    click.echo(laboratory_page(context.book()), nl=False)


@report.command("contracts")
@click.option("--customer", default=None, help="only this customer.")
@pass_context
def report_contracts(context: Context, customer: str | None) -> None:
    """Where the contracts stand, in all three tonnages."""
    click.echo(contract_page(context.book(), customer=customer), nl=False)


@report.command("calls")
@_window_options
@pass_context
def report_calls(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> None:
    """What customers have asked for against each contract."""
    click.echo(call_page(context.book(), _window(context, opens, closes)), nl=False)


@click.group()
def trace() -> None:
    """Genealogy, both ways along the chain."""


@trace.command("forward")
@click.argument("ticket")
@pass_context
def trace_forward(context: Context, ticket: str) -> None:
    """Where a lorry load of barley ended up, for a recall."""
    click.echo(recall_page(context.book(), ticket), nl=False)


@trace.command("back")
@click.argument("shipment")
@pass_context
def trace_back(context: Context, shipment: str) -> None:
    """What went into a shipment, for a customer complaint."""
    click.echo(investigation_page(context.book(), shipment), nl=False)
