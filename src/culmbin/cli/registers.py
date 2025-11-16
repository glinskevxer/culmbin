"""Commands over the registers: parties, varieties and vessels.

These are the ones somebody runs twice a year, so they are plain and they
say what they did. Every one of them either writes a row or explains why it
will not.
"""

from __future__ import annotations

import datetime as dt

import click

from culmbin.cli.context import Context, echo_lines, pass_context
from culmbin.model.enums import Approval, Habit, Role, VesselKind
from culmbin.model.party import Party
from culmbin.model.plant import Vessel
from culmbin.model.variety import Variety
from culmbin.report.layout import Align, Column, table
from culmbin.store.parties import add_party, close_party, get_party, list_parties
from culmbin.store.varieties import (
    add_variety,
    get_variety,
    list_varieties,
    promote_variety,
    withdraw_variety,
)
from culmbin.store.vessels import add_vessel, get_vessel, list_vessels, retire_vessel

LIST_APPROVALS = [Approval.APPROVED.value, Approval.PROVISIONAL.value]
NEW_APPROVALS = [*LIST_APPROVALS, Approval.UNDER_TEST.value]


@click.group()
def party() -> None:
    """Growers, merchants, customers and hauliers."""


@party.command("add")
@click.argument("code")
@click.argument("name")
@click.option(
    "--role",
    type=click.Choice([item.value for item in Role]),
    required=True,
    help="what they are to us.",
)
@click.option("--holding", default=None, help="the holding number, for a grower.")
@click.option("--note", default="", help="anything worth writing down.")
@pass_context
def party_add(
    context: Context, code: str, name: str, role: str, holding: str | None, note: str
) -> None:
    """Put somebody in the register."""
    written = add_party(
        context.book(),
        Party(code, name, Role(role), context.on, holding=holding, note=note),
    )
    click.echo(f"{written} added as a {written.role}.")


@party.command("close")
@click.argument("code")
@pass_context
def party_close(context: Context, code: str) -> None:
    """Stop trading with somebody from today."""
    closed = close_party(context.book(), code, context.on)
    click.echo(f"{closed} closed on {closed.closed}.")


@party.command("list")
@click.option(
    "--role",
    type=click.Choice([item.value for item in Role]),
    default=None,
    help="only this role.",
)
@click.option("--trading/--all", default=False, help="only those still trading today.")
@pass_context
def party_list(context: Context, role: str | None, trading: bool) -> None:
    """List the register."""
    register = list_parties(context.book(), None if role is None else Role(role))
    parties = register.trading_on(context.on) if trading else tuple(register)
    echo_lines(
        table(
            [Column("code"), Column("name"), Column("role"), Column("opened"), Column("closed")],
            [
                [
                    item.code,
                    item.name,
                    str(item.role),
                    item.opened.isoformat(),
                    "" if item.closed is None else item.closed.isoformat(),
                ]
                for item in parties
            ],
        )
    )


@party.command("show")
@click.argument("code")
@pass_context
def party_show(context: Context, code: str) -> None:
    """Say everything about one party."""
    found = get_party(context.book(), code)
    click.echo(f"{found}")
    click.echo(f"role      {found.role}")
    click.echo(f"opened    {found.opened}")
    if found.closed is not None:
        click.echo(f"closed    {found.closed}")
    if found.holding is not None:
        click.echo(f"holding   {found.holding}")
    if found.note:
        click.echo(f"note      {found.note}")
    click.echo(f"trading   {'yes' if found.trading_on(context.on) else 'no'}")


@click.group()
def variety() -> None:
    """The approved list of barley varieties."""


@variety.command("add")
@click.argument("code")
@click.argument("name")
@click.option(
    "--habit",
    type=click.Choice([item.value for item in Habit]),
    default="spring",
    help="spring or winter barley, which are contracted separately.",
)
@click.option(
    "--approval",
    type=click.Choice(NEW_APPROVALS),
    default=Approval.UNDER_TEST.value,
    help="how far up the approved list it has got.",
)
@pass_context
def variety_add(context: Context, code: str, name: str, habit: str, approval: str) -> None:
    """Put a variety on the list."""
    written = add_variety(
        context.book(), Variety(code, name, Habit(habit), Approval(approval), context.on)
    )
    click.echo(f"{written} added as {written.approval}.")


@variety.command("promote")
@click.argument("code")
@click.argument(
    "approval", type=click.Choice([Approval.APPROVED.value, Approval.PROVISIONAL.value])
)
@pass_context
def variety_promote(context: Context, code: str, approval: str) -> None:
    """Move a variety along the list."""
    moved = promote_variety(context.book(), code, Approval(approval))
    click.echo(f"{moved} is now {moved.approval}.")


@variety.command("withdraw")
@click.argument("code")
@pass_context
def variety_withdraw(context: Context, code: str) -> None:
    """Take a variety off the list from today."""
    gone = withdraw_variety(context.book(), code, context.on)
    click.echo(f"{gone} withdrawn on {gone.withdrawn}.")


@variety.command("list")
@click.option("--on-list/--all", default=False, help="only those on the list today.")
@pass_context
def variety_list(context: Context, on_list: bool) -> None:
    """List the varieties."""
    listing = list_varieties(context.book())
    items = listing.on_the_list_on(context.on) if on_list else tuple(listing)
    echo_lines(
        table(
            [Column("code"), Column("name"), Column("habit"), Column("approval"), Column("listed")],
            [
                [
                    item.code,
                    item.name,
                    str(item.habit),
                    str(item.approval),
                    item.listed.isoformat(),
                ]
                for item in items
            ],
        )
    )


@variety.command("show")
@click.argument("code")
@pass_context
def variety_show(context: Context, code: str) -> None:
    """Say everything about one variety."""
    found = get_variety(context.book(), code)
    click.echo(f"{found}")
    click.echo(f"approval  {found.approval}")
    click.echo(f"listed    {found.listed}")
    if found.withdrawn is not None:
        click.echo(f"withdrawn {found.withdrawn}")
    click.echo(f"on list   {'yes' if found.on_the_list_on(context.on) else 'no'}")


@click.group()
def vessel() -> None:
    """Steeps, boxes, floors and kilns."""


@vessel.command("add")
@click.argument("code")
@click.argument("name")
@click.option("--kind", type=click.Choice([item.value for item in VesselKind]), required=True)
@click.option("--charge", type=float, default=None, help="tonnes, for a steep.")
@click.option("--area", type=float, default=None, help="square metres, for a bed.")
@click.option("--depth", type=float, default=None, help="centimetres, for a bed.")
@click.option(
    "--commissioned",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="when it went into service. Defaults to today.",
)
@pass_context
def vessel_add(
    context: Context,
    code: str,
    name: str,
    kind: str,
    charge: float | None,
    area: float | None,
    depth: float | None,
    commissioned: dt.datetime | None,
) -> None:
    """Put a vessel in the register.

    A steep takes a charge in tonnes. Everything else takes an area and a
    depth, because what a bed holds is a property of the bed and the depth
    rather than of the vessel.
    """
    built = context.on if commissioned is None else commissioned.date()
    written = add_vessel(
        context.book(),
        Vessel(
            code=code,
            name=name,
            kind=VesselKind(kind),
            commissioned=built,
            charge_limit_t=charge,
            floor_area_m2=area,
            depth_limit_cm=depth,
        ),
    )
    click.echo(f"{written.code} added, holding {written.limit_t:.1f}t.")


@vessel.command("retire")
@click.argument("code")
@pass_context
def vessel_retire(context: Context, code: str) -> None:
    """Take a vessel out of service from today."""
    gone = retire_vessel(context.book(), code, context.on)
    click.echo(f"{gone.code} retired on {gone.retired}.")


@vessel.command("list")
@click.option(
    "--kind",
    type=click.Choice([item.value for item in VesselKind]),
    default=None,
    help="only this kind of vessel.",
)
@pass_context
def vessel_list(context: Context, kind: str | None) -> None:
    """List the plant."""
    plant = list_vessels(context.book(), None if kind is None else VesselKind(kind))
    echo_lines(
        table(
            [
                Column("code"),
                Column("name"),
                Column("kind"),
                Column("holds", Align.RIGHT),
                Column("in service"),
            ],
            [
                [
                    item.code,
                    item.name,
                    str(item.kind),
                    f"{item.limit_t:.1f}",
                    "yes" if item.in_service_on(context.on) else "no",
                ]
                for item in plant
            ],
        )
    )


@vessel.command("show")
@click.argument("code")
@pass_context
def vessel_show(context: Context, code: str) -> None:
    """Say everything about one vessel, including what it holds at a depth."""
    found = get_vessel(context.book(), code)
    click.echo(f"{found.code} {found.name}")
    click.echo(f"kind      {found.kind}")
    click.echo(f"holds     {found.limit_t:.1f}t")
    if found.sized_by_area:
        assert found.floor_area_m2 is not None
        assert found.depth_limit_cm is not None
        click.echo(f"bed       {found.floor_area_m2:.0f}m2 to {found.depth_limit_cm:.0f}cm")
        for depth in (30.0, 60.0, found.depth_limit_cm):
            if depth <= found.depth_limit_cm:
                click.echo(f"  at {depth:.0f}cm  {found.tonnes_at_depth(depth):.1f}t")
    click.echo(f"in service {'yes' if found.in_service_on(context.on) else 'no'}")
