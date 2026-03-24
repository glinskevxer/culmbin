"""Commands for the barley yard: silos, tipping and charging out of one."""

from __future__ import annotations

import click

from culmbin.cli.context import Context, pass_context
from culmbin.model.enums import MaltStyle
from culmbin.model.silo import Silo
from culmbin.process.yard import charge_from_silo, plan_charge
from culmbin.report.yard import yard_page
from culmbin.store.silos import add_silo, get_silo, holding_in, sweep, tip

STYLES = [item.value for item in MaltStyle]


@click.group()
def silo() -> None:
    """The silos barley is kept in between the weighbridge and the steep."""


@silo.command("add")
@click.argument("code")
@click.option("--capacity", type=float, required=True, help="tonnes.")
@pass_context
def silo_add(context: Context, code: str, capacity: float) -> None:
    """Put a silo in the register."""
    add_silo(context.book(), Silo(code, capacity, commissioned=context.on))
    click.echo(f"{code} added, holding {capacity:.0f}t.")


@silo.command("tip")
@click.argument("code")
@click.argument("ticket")
@pass_context
def silo_tip(context: Context, code: str, ticket: str) -> None:
    """Tip an accepted load into a silo.

    What goes in is the settled tonnage rather than the weighbridge net,
    because the screenings went in a different bin.
    """
    after = tip(context.book(), code, ticket, context.on)
    holding = holding_in(context.book(), code)
    context.note("tipped", ticket, f"into {code}")
    click.echo(f"{holding}")
    if after.mixed:
        click.echo(f"{code} is now MIXED and cannot charge a piece at all.")


@silo.command("sweep")
@click.argument("code")
@pass_context
def silo_sweep(context: Context, code: str) -> None:
    """Take the mixed mark off a silo that has been emptied and swept out."""
    sweep(context.book(), code)
    click.echo(f"{code} swept, segregation mark cleared.")


@silo.command("show")
@click.argument("code")
@pass_context
def silo_show(context: Context, code: str) -> None:
    """Say what is in a silo and which loads it came off."""
    found = get_silo(context.book(), code)
    holding = holding_in(context.book(), code)
    click.echo(f"{found}")
    click.echo(f"holding   {holding}")
    for share in holding.shares:
        click.echo(f"  {share.ticket:<12}{share.tonnes:>10.2f}t")


@silo.command("list")
@pass_context
def silo_list(context: Context) -> None:
    """Print the yard page."""
    click.echo(yard_page(context.book()), nl=False)


@silo.command("draw")
@click.argument("code")
@click.argument("piece")
@click.option("--tonnes", type=float, required=True, help="the steep charge.")
@click.option("--variety", required=True, help="what the piece is to be.")
@click.option("--crop", type=int, required=True, help="the crop year.")
@click.option("--style", type=click.Choice(STYLES), required=True, help="what it is to become.")
@click.option("--steep", required=True, help="the vessel it goes into.")
@click.option("--programme", required=True, help="the steep programme.")
@click.option("--schedule", required=True, help="the germination schedule.")
@click.option("--curve", required=True, help="the kiln curve.")
@click.option("--share", is_flag=True, help="allow a second piece in the same vessel.")
@click.option("--dry-run", is_flag=True, help="say what it would carry and write nothing.")
@pass_context
def silo_draw(
    context: Context,
    code: str,
    piece: str,
    tonnes: float,
    variety: str,
    crop: int,
    style: str,
    steep: str,
    programme: str,
    schedule: str,
    curve: str,
    share: bool,
    dry_run: bool,
) -> None:
    """Charge a steep out of a silo, writing down where the barley came from.

    The moisture is not asked for. It is what is in the silo, because a typed
    moisture and a silo moisture that disagree cannot be settled six weeks
    later.
    """
    if dry_run:
        for part in plan_charge(context.book(), code, tonnes, variety):
            click.echo(f"  {part.ticket:<12}{part.tonnes:>10.3f}t")
        return
    charged = charge_from_silo(
        context.book(),
        piece,
        code,
        variety,
        crop,
        MaltStyle(style),
        tonnes,
        steep,
        context.on,
        programme,
        schedule,
        curve,
        share=share,
    )
    click.echo(
        f"{charged} charged at {charged.charge_moisture:.2f}%, "
        f"{charged.charge_dry_tonnes:.2f}t dry matter."
    )
