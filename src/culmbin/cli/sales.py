"""Commands for the sales desk: contracts, call-offs and getting malt out.

`ship allocate` is the one that does the work. It refuses a lot for one of
four reasons and says which, because "cannot ship" is not an answer anybody
can act on and "L-1 is 6.20 on colour and lager 2025 says colour 2.5 to 4.5
EBC" is.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import click

from culmbin.cli.context import Context, echo_lines, pass_context
from culmbin.cli.window import week_from, window_options
from culmbin.model.enums import ContractState
from culmbin.model.sales import Call, Contract
from culmbin.report.layout import Align, Column, table
from culmbin.report.sales import contract_page, diary_page
from culmbin.sales.desk import allocate, availability, cancel, despatch, load
from culmbin.store.contracts import (
    add_call,
    add_contract,
    get_contract,
    list_calls,
    position,
    set_state,
)
from culmbin.store.shipments import get_shipment, list_shipments
from culmbin.units.season import Window


@click.group()
def contract() -> None:
    """Agreements to sell malt."""


@contract.command("add")
@click.argument("code")
@click.argument("customer")
@click.option("--spec", "specification", required=True)
@click.option("--tonnes", type=float, required=True)
@click.option("--price", required=True, help="per contract tonne.")
@click.option(
    "--moisture",
    type=float,
    default=4.5,
    show_default=True,
    help="the moisture the contract tonne is written at.",
)
@click.option(
    "--from",
    "opens",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    help="the first day of the window.",
)
@click.option(
    "--to",
    "closes",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    help="the last day of the window.",
)
@click.option("--variety", default=None, help="only a lot declaring this variety can serve it.")
@pass_context
def contract_add(
    context: Context,
    code: str,
    customer: str,
    specification: str,
    tonnes: float,
    price: str,
    moisture: float,
    opens: dt.datetime,
    closes: dt.datetime,
    variety: str | None,
) -> None:
    """Write a contract, in draft."""
    written = add_contract(
        context.book(),
        Contract(
            code=code,
            customer=customer,
            specification=specification,
            tonnes=tonnes,
            moisture=moisture,
            price_per_tonne=Decimal(price),
            window=Window(opens.date(), closes.date()),
            signed=context.on,
            state=ContractState.DRAFT,
            variety=variety,
        ),
    )
    click.echo(f"{written} drafted, worth {written.value} at {written.moisture:.1f}% moisture.")


@contract.command("sign")
@click.argument("code")
@pass_context
def contract_sign(context: Context, code: str) -> None:
    """Sign a contract so malt can ship against it."""
    signed = set_state(context.book(), code, ContractState.SIGNED)
    click.echo(f"{signed.code} signed.")


@contract.command("close")
@click.argument("code")
@pass_context
def contract_close(context: Context, code: str) -> None:
    """Close a contract. It does not reopen."""
    set_state(context.book(), code, ContractState.CLOSED)
    click.echo(f"{code} closed.")


@contract.command("list")
@click.option("--customer", default=None, help="only this customer.")
@pass_context
def contract_list(context: Context, customer: str | None) -> None:
    """Print where the contracts stand."""
    click.echo(contract_page(context.book(), customer=customer), nl=False)


@contract.command("show")
@click.argument("code")
@pass_context
def contract_show(context: Context, code: str) -> None:
    """Say everything about one contract, including all three tonnages."""
    found = get_contract(context.book(), code)
    where = position(context.book(), code)
    click.echo(f"{found}")
    click.echo(f"state      {found.state}")
    click.echo(f"spec       {found.specification}")
    click.echo(f"moisture   {found.moisture:.1f}%")
    click.echo(f"price      {found.price_per_tonne} a tonne, {found.value} in all")
    click.echo(f"window     {found.window}")
    if found.variety is not None:
        click.echo(f"variety    {found.variety}")
    click.echo(f"signed     {where.contracted:.1f}t")
    click.echo(f"delivered  {where.delivered:.1f}t")
    click.echo(f"committed  {where.committed:.1f}t")
    click.echo(f"left       {where.outstanding:.1f}t")


@click.group()
def call() -> None:
    """Customer call-offs against a contract."""


@call.command("add")
@click.argument("code")
@click.argument("contract_code")
@click.option("--tonnes", type=float, required=True)
@click.option(
    "--from",
    "opens",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    help="the first day of the window.",
)
@click.option(
    "--to",
    "closes",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    help="the last day of the window.",
)
@pass_context
def call_add(
    context: Context,
    code: str,
    contract_code: str,
    tonnes: float,
    opens: dt.datetime,
    closes: dt.datetime,
) -> None:
    """Record what the customer has asked for and when."""
    written = add_call(
        context.book(),
        Call(code, contract_code, tonnes, Window(opens.date(), closes.date()), context.on),
    )
    click.echo(f"{written} against {contract_code}.")


@call.command("list")
@click.option("--contract", "contract_code", default=None, help="only against this contract.")
@pass_context
def call_list(context: Context, contract_code: str | None) -> None:
    """List the call-offs."""
    echo_lines(
        table(
            [Column("call"), Column("contract"), Column("tonnes", Align.RIGHT), Column("week")],
            [
                [item.code, item.contract, f"{item.tonnes:.0f}", str(item.wanted)]
                for item in list_calls(context.book(), contract=contract_code)
            ],
        )
    )


@click.group()
def ship() -> None:
    """Malt going out of the gate."""


@ship.command("allocate")
@click.argument("code")
@click.argument("contract_code")
@click.argument("lot")
@click.option("--tonnes", type=float, required=True)
@click.option("--call", "call_code", default=None, help="the call-off it serves.")
@click.option("--haulier", default=None, help="who is carrying it.")
@click.option("--vehicle", default=None, help="the registration on the ticket.")
@pass_context
def ship_allocate(
    context: Context,
    code: str,
    contract_code: str,
    lot: str,
    tonnes: float,
    call_code: str | None,
    haulier: str | None,
    vehicle: str | None,
) -> None:
    """Put a lot against a contract, with all four checks first."""
    shipment = allocate(
        context.book(),
        code,
        contract_code,
        lot,
        tonnes,
        context.on,
        call=call_code,
        haulier=haulier,
        vehicle=vehicle,
    )
    free = availability(context.book(), lot)
    context.note("allocated", code, f"{tonnes:.2f}t of {lot} to {contract_code}")
    click.echo(f"{shipment} planned, {free.free_tonnes:.2f}t left on {lot}.")


@ship.command("load")
@click.argument("code")
@click.option("--tonnes", type=float, required=True, help="off the weighbridge.")
@click.option("--moisture", type=float, required=True)
@pass_context
def ship_load(context: Context, code: str, tonnes: float, moisture: float) -> None:
    """Weigh a load and take the malt out of the bin."""
    loaded = load(context.book(), code, tonnes, moisture, context.on)
    contract_code = get_contract(context.book(), loaded.contract)
    drawn = loaded.contract_tonnes(contract_code.moisture)
    context.note("loaded", code, f"{tonnes:.2f}t at {moisture:.2f}%")
    click.echo(f"{loaded} loaded.")
    click.echo(
        f"draws {drawn:.3f} contract tonnes at {contract_code.moisture:.1f}%, "
        f"worth {loaded.value(contract_code.price_per_tonne, contract_code.moisture)}."
    )


@ship.command("despatch")
@click.argument("code")
@pass_context
def ship_despatch(context: Context, code: str) -> None:
    """Send a loaded shipment out. It does not change again afterwards."""
    despatch(context.book(), code)
    context.note("despatched", code)
    click.echo(f"{code} despatched.")


@ship.command("cancel")
@click.argument("code")
@pass_context
def ship_cancel(context: Context, code: str) -> None:
    """Give up a slot in the loading diary and put the malt back."""
    shipment = cancel(context.book(), code)
    free = availability(context.book(), shipment.lot)
    context.note("cancelled", code)
    click.echo(f"{code} cancelled, {free.free_tonnes:.2f}t back on {shipment.lot}.")


@ship.command("diary")
@window_options
@pass_context
def ship_diary(context: Context, opens: dt.datetime | None, closes: dt.datetime | None) -> None:
    """Print the loading diary, a week ahead by default."""
    week = week_from(context, opens, closes)
    click.echo(diary_page(context.book(), week.start, week.end), nl=False)


@ship.command("show")
@click.argument("code")
@pass_context
def ship_show(context: Context, code: str) -> None:
    """Say everything about one shipment."""
    found = get_shipment(context.book(), code)
    against = get_contract(context.book(), found.contract)
    click.echo(f"{found}")
    click.echo(f"contract   {found.contract} ({against.customer})")
    click.echo(f"lot        {found.lot}")
    click.echo(f"state      {found.state}")
    click.echo(f"weighbridge {found.tonnes:.2f}t at {found.moisture:.2f}%")
    click.echo(
        f"contract   {found.contract_tonnes(against.moisture):.3f}t at {against.moisture:.1f}%"
    )
    if found.call is not None:
        click.echo(f"call       {found.call}")


@ship.command("list")
@click.option("--contract", "contract_code", default=None, help="only against this contract.")
@click.option("--lot", default=None, help="only out of this lot.")
@pass_context
def ship_list(context: Context, contract_code: str | None, lot: str | None) -> None:
    """List the shipments."""
    echo_lines(
        table(
            [
                Column("shipment"),
                Column("contract"),
                Column("lot"),
                Column("tonnes", Align.RIGHT),
                Column("day"),
                Column("state"),
            ],
            [
                [
                    item.code,
                    item.contract,
                    item.lot,
                    f"{item.tonnes:.2f}",
                    item.despatched.isoformat(),
                    str(item.state),
                ]
                for item in list_shipments(context.book(), contract=contract_code, lot=lot)
            ],
        )
    )
