"""Commands for the quality desk: complaints and what came of them."""

from __future__ import annotations

import datetime as dt

import click

from culmbin.cli.context import Context, pass_context
from culmbin.cli.window import window_for, window_options
from culmbin.model.complaint import Complaint
from culmbin.model.enums import ComplaintKind, ComplaintState
from culmbin.report.quality import quality_page
from culmbin.store.complaints import attach, close, get_complaint, investigate, raise_complaint
from culmbin.trace.walk import backward_from_shipment

CLOSING = [
    ComplaintState.UPHELD.value,
    ComplaintState.REJECTED.value,
    ComplaintState.WITHDRAWN.value,
]


@click.group()
def complaint() -> None:
    """Customer complaints and what came of them."""


@complaint.command("raise")
@click.argument("code")
@click.argument("customer")
@click.argument("summary")
@click.option(
    "--about",
    type=click.Choice([item.value for item in ComplaintKind]),
    required=True,
    help="what the customer says is wrong.",
)
@click.option("--shipment", default=None, help="the load it is about, if anybody knows.")
@pass_context
def complaint_raise(
    context: Context, code: str, customer: str, summary: str, about: str, shipment: str | None
) -> None:
    """Write down a telephone call.

    The shipment is optional because a customer ringing about the malt sent
    in March has not given one, and recording a guess is worse than
    recording that nobody knew.
    """
    written = raise_complaint(
        context.book(),
        Complaint(
            code=code,
            customer=customer,
            kind=ComplaintKind(about),
            raised=context.on,
            summary=summary,
            shipment=shipment,
        ),
    )
    context.note("complaint raised", code, summary)
    click.echo(f"{written}")
    if not written.traceable and written.about_the_malt:
        click.echo("no shipment against it, so it cannot be walked back yet.")


@complaint.command("attach")
@click.argument("code")
@click.argument("shipment")
@pass_context
def complaint_attach(context: Context, code: str, shipment: str) -> None:
    """Put a shipment on a complaint and say what went into it."""
    attach(context.book(), code, shipment)
    walk = backward_from_shipment(context.book(), shipment)
    click.echo(f"{code} is against {shipment}, lot {walk.lot}.")
    if walk.growers:
        click.echo(f"growers behind it: {', '.join(walk.growers)}")
    else:
        click.echo("no lorry loads are recorded against the pieces in that lot.")


@complaint.command("investigate")
@click.argument("code")
@pass_context
def complaint_investigate(context: Context, code: str) -> None:
    """Move a complaint from open to being looked into."""
    investigate(context.book(), code)
    click.echo(f"{code} is being looked into.")


@complaint.command("close")
@click.argument("code")
@click.argument("state", type=click.Choice(CLOSING))
@click.option("--finding", required=True, help="what was found.")
@pass_context
def complaint_close(context: Context, code: str, state: str, finding: str) -> None:
    """Close a complaint, with what was found written down."""
    closed = close(context.book(), code, ComplaintState(state), context.on, finding)
    context.note("complaint closed", code, f"{state}: {finding}")
    click.echo(f"{code} closed as {state} after {closed.days_open(context.on)} days.")


@complaint.command("show")
@click.argument("code")
@pass_context
def complaint_show(context: Context, code: str) -> None:
    """Say everything about one complaint."""
    found = get_complaint(context.book(), code)
    click.echo(f"{found}")
    click.echo(f"raised    {found.raised}")
    click.echo(f"summary   {found.summary}")
    if found.shipment is not None:
        click.echo(f"shipment  {found.shipment}")
    if found.closed is not None:
        click.echo(f"closed    {found.closed} after {found.days_open(context.on)} days")
        click.echo(f"finding   {found.finding}")
    else:
        click.echo(f"open      {found.days_open(context.on)} days")


@complaint.command("list")
@window_options
@pass_context
def complaint_list(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> None:
    """Print the quality page."""
    window = window_for(context, opens, closes)
    click.echo(quality_page(context.book(), window, context.on), nl=False)
