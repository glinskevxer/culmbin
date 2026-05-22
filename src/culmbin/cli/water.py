"""Commands for the water meter."""

from __future__ import annotations

import datetime as dt

import click

from culmbin.cli.context import Context, echo_lines, pass_context
from culmbin.cli.window import window_for, window_options
from culmbin.report.water import water_page
from culmbin.store.water import (
    get_water,
    record_water,
    unmetered,
)


@click.group()
def water() -> None:
    """What the water meter read across a steep."""


@water.command("record")
@click.argument("piece")
@click.option("--m3", "metered_m3", type=float, required=True, help="cubic metres off the meter.")
@click.option("--note", "detail", default="", help="anything worth writing down.")
@pass_context
def water_record(context: Context, piece: str, metered_m3: float, detail: str) -> None:
    """Write down what the water meter read across one steep."""
    use = record_water(context.book(), piece, metered_m3, context.on, detail)
    click.echo(f"{use}")
    click.echo(
        f"the barley kept {use.taken_up_m3:.1f}m3 and {use.to_drain_m3:.1f}m3 went to drain."
    )
    if use.heavy:
        click.echo("that is over the band, which is a bill rather than a fault.")
    context.note("metered water", piece, f"{metered_m3:.1f}m3")


@water.command("show")
@click.argument("piece")
@pass_context
def water_show(context: Context, piece: str) -> None:
    """Say everything about one steep's water."""
    use = get_water(context.book(), piece)
    click.echo(f"{piece}")
    click.echo(f"metered   {use.metered_m3:.1f} m3")
    click.echo(f"kept      {use.taken_up_m3:.1f} m3")
    click.echo(f"to drain  {use.to_drain_m3:.1f} m3 ({use.drain_share * 100:.0f}%)")
    click.echo(f"a tonne   {use.specific_m3_per_tonne:.2f} m3")


@water.command("list")
@window_options
@pass_context
def water_list(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> None:
    """Print the water page."""
    click.echo(water_page(context.book(), window_for(context, opens, closes)), nl=False)


@water.command("waiting")
@pass_context
def water_waiting(context: Context) -> None:
    """Every cast piece with no water reading against it."""
    waiting = unmetered(context.book())
    if not waiting:
        click.echo("every cast piece has a meter reading.")
        return
    echo_lines(list(waiting))
