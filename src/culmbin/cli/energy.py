"""Commands for the gas meter."""

from __future__ import annotations

import datetime as dt

import click

from culmbin.cli.context import Context, pass_context
from culmbin.report.energy import energy_page
from culmbin.store.energy import get_run, record_run, suspect_runs, unmetered
from culmbin.units.season import Window


@click.group()
def gas() -> None:
    """What the meter read across a kiln run."""


@gas.command("record")
@click.argument("piece")
@click.option("--kiln", required=True, help="the kiln it ran on.")
@click.option("--m3", "gas_m3", type=float, required=True, help="cubic metres off the meter.")
@click.option("--note", default="", help="anything worth writing down.")
@pass_context
def gas_record(context: Context, piece: str, kiln: str, gas_m3: float, note: str) -> None:
    """Write down what the meter read across one piece's time on a kiln.

    Only worth doing once the piece has been stripped, because half the
    arithmetic needs the weight that came off the kiln.
    """
    run = record_run(context.book(), piece, kiln, gas_m3, context.on, note)
    click.echo(f"{piece} on {kiln}: {run.gas_m3:.0f}m3 for {run.water_kg / 1000:.2f}t of water.")
    click.echo(
        f"efficiency {run.efficiency * 100:.0f}%, "
        f"{run.specific_energy_kwh_per_tonne:.0f} kWh a tonne of malt."
    )
    if run.suspect:
        click.echo("that is outside what a kiln can do. Somebody should look at the meter.")


@gas.command("show")
@click.argument("piece")
@pass_context
def gas_show(context: Context, piece: str) -> None:
    """Say everything about one kiln run."""
    run = get_run(context.book(), piece)
    click.echo(f"{piece}")
    click.echo(f"cast at    {run.green_moisture:.1f}% on {run.green_tonnes:.2f}t")
    click.echo(f"off kiln   {run.malt_moisture:.1f}% on {run.malt_tonnes:.2f}t")
    click.echo(f"water      {run.water_kg / 1000:.2f}t")
    click.echo(f"heat wanted {run.heat_wanted_mj:.0f} MJ")
    click.echo(f"gas burnt  {run.gas_m3:.0f}m3, {run.heat_burnt_mj:.0f} MJ")
    click.echo(f"efficiency {run.efficiency * 100:.0f}%")
    click.echo(f"specific   {run.specific_energy_kwh_per_tonne:.0f} kWh a tonne")


@gas.command("waiting")
@pass_context
def gas_waiting(context: Context) -> None:
    """Every stripped piece with no meter reading against it."""
    waiting = unmetered(context.book())
    if not waiting:
        click.echo("every stripped piece has a meter reading.")
        return
    for piece in waiting:
        click.echo(piece)


@gas.command("suspect")
@pass_context
def gas_suspect(context: Context) -> None:
    """Every run whose efficiency is outside what a kiln can do."""
    runs = suspect_runs(context.book())
    if not runs:
        click.echo("every run is inside the band.")
        return
    for run in runs:
        click.echo(f"{run.piece}  {run.efficiency * 100:.0f}%")


@gas.command("list")
@click.option(
    "--from",
    "opens",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="the first day. Defaults to the first of the month.",
)
@click.option(
    "--to",
    "closes",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="the last day. Defaults to the day being worked as.",
)
@pass_context
def gas_list(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> None:
    """Print the gas page."""
    end = context.on if closes is None else closes.date()
    start = end.replace(day=1) if opens is None else opens.date()
    click.echo(energy_page(context.book(), Window(start, end)), nl=False)
