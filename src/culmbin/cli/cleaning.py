"""Commands for the cleaning book."""

from __future__ import annotations

import click

from culmbin.cli.context import Context, pass_context
from culmbin.report.cleaning import cleaning_page, vessel_history
from culmbin.store.cleaning import record_cleaning, set_interval, standing


@click.group()
def clean() -> None:
    """When a vessel was last cleaned and how often it should be."""


@clean.command("record")
@click.argument("vessel")
@click.option("--by", "by_whom", required=True, help="who did it.")
@click.option("--note", default="", help="what was done.")
@pass_context
def clean_record(context: Context, vessel: str, by_whom: str, note: str) -> None:
    """Write down that a vessel was cleaned."""
    record_cleaning(context.book(), vessel, context.on, by_whom, note)
    context.note("cleaned", vessel, note or "no note")
    click.echo(f"{vessel} cleaned on {context.on} by {by_whom}.")


@clean.command("interval")
@click.argument("vessel")
@click.option("--days", type=int, required=True, help="clean at least this often.")
@click.option("--pieces", type=int, required=True, help="and at least this often.")
@pass_context
def clean_interval(context: Context, vessel: str, days: int, pieces: int) -> None:
    """Say how often a vessel has to be cleaned, and start policing it.

    Until an interval is set the vessel is not policed at all, so this is
    what switches the rule on for one vessel.
    """
    set_interval(context.book(), vessel, days, pieces)
    click.echo(f"{vessel} is now policed at {days} days or {pieces} pieces, whichever first.")


@clean.command("due")
@pass_context
def clean_due(context: Context) -> None:
    """Print the cleaning page."""
    click.echo(cleaning_page(context.book(), context.on), nl=False)


@clean.command("show")
@click.argument("vessel")
@pass_context
def clean_show(context: Context, vessel: str) -> None:
    """Where a vessel stands, and every cleaning it has had."""
    where = standing(context.book(), vessel)
    click.echo(where.why(context.on))
    click.echo(vessel_history(context.book(), vessel), nl=False)
