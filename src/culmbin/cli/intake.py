"""Commands for the intake office: standards, purchases and lorries."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import click

from culmbin.cli.context import Context, echo_lines, pass_context
from culmbin.cli.values import parse_results
from culmbin.intake.desk import grade_load, settle_load, take_sample, weigh_in
from culmbin.intake.standard import Standard
from culmbin.model.enums import Material, RejectionReason
from culmbin.model.intake import Delivery, Purchase
from culmbin.model.results import analysis_of
from culmbin.report.layout import Align, Column, table
from culmbin.store.deliveries import get_delivery, list_deliveries, record_harvest, unsampled
from culmbin.store.gradings import get_grading, ungraded
from culmbin.store.purchases import (
    add_purchase,
    extend_window,
    get_purchase,
    list_purchases,
    outstanding,
    settled_against,
)
from culmbin.store.standards import add_standard, copy_standard, get_standard, list_standards
from culmbin.units.season import Window


@click.group()
def standard() -> None:
    """The intake quality standards a purchase is bought against."""


@standard.command("add")
@click.argument("name")
@click.option("--moisture-base", type=float, default=12.5, show_default=True)
@click.option("--moisture-reject", type=float, default=20.0, show_default=True)
@click.option("--nitrogen-min", type=float, default=1.35, show_default=True)
@click.option("--nitrogen-max", type=float, default=1.85, show_default=True)
@click.option("--nitrogen-reject", type=float, default=2.05, show_default=True)
@click.option("--screenings-free", type=float, default=2.0, show_default=True)
@click.option("--screenings-reject", type=float, default=5.0, show_default=True)
@click.option("--germination-floor", type=float, default=98.0, show_default=True)
@click.option("--energy-floor", type=float, default=95.0, show_default=True)
@pass_context
def standard_add(
    context: Context,
    name: str,
    moisture_base: float,
    moisture_reject: float,
    nitrogen_min: float,
    nitrogen_max: float,
    nitrogen_reject: float,
    screenings_free: float,
    screenings_reject: float,
    germination_floor: float,
    energy_floor: float,
) -> None:
    """Write a quality standard.

    A standard is not edited afterwards. Settlements quote it, so next
    season's is a new name and `standard copy` is how it starts.
    """
    written = add_standard(
        context.book(),
        Standard(
            name=name,
            moisture_base=moisture_base,
            moisture_reject=moisture_reject,
            nitrogen_min=nitrogen_min,
            nitrogen_max=nitrogen_max,
            nitrogen_reject=nitrogen_reject,
            screenings_free=screenings_free,
            screenings_reject=screenings_reject,
            germination_floor=germination_floor,
            energy_floor=energy_floor,
        ),
    )
    click.echo(f"{written.name} added.")


@standard.command("copy")
@click.argument("name")
@click.argument("into")
@pass_context
def standard_copy(context: Context, name: str, into: str) -> None:
    """Start next season's standard off last season's thresholds."""
    copy_standard(context.book(), name, into)
    click.echo(f"{into} copied from {name}.")


@standard.command("list")
@pass_context
def standard_list(context: Context) -> None:
    """List the standards."""
    echo_lines(
        table(
            [
                Column("name"),
                Column("moisture", Align.RIGHT),
                Column("nitrogen band"),
                Column("screenings", Align.RIGHT),
                Column("germination", Align.RIGHT),
            ],
            [
                [
                    item.name,
                    f"{item.moisture_base:.1f}/{item.moisture_reject:.1f}",
                    f"{item.nitrogen_min:.2f}-{item.nitrogen_max:.2f}",
                    f"{item.screenings_free:.1f}",
                    f"{item.germination_floor:.0f}",
                ]
                for item in list_standards(context.book())
            ],
        )
    )


@standard.command("show")
@click.argument("name")
@pass_context
def standard_show(context: Context, name: str) -> None:
    """Say every threshold on one standard, rejections apart from deductions."""
    found = get_standard(context.book(), name)
    click.echo(f"{found.name}")
    click.echo("rejects at")
    click.echo(f"  moisture over    {found.moisture_reject:.1f}")
    click.echo(f"  screenings over  {found.screenings_reject:.1f}")
    click.echo(f"  nitrogen over    {found.nitrogen_reject:.2f}")
    click.echo(f"  admixture over   {found.admixture_reject:.1f}")
    click.echo(f"  germination under {found.germination_floor:.0f}")
    click.echo(f"  new crop energy under {found.energy_floor:.0f}")
    click.echo("deducts")
    click.echo(f"  drying per point {found.drying_per_point}")
    click.echo(f"  nitrogen over {found.nitrogen_max:.2f}, {found.nitrogen_per_step} a step")
    click.echo(f"  screenings over {found.screenings_free:.1f} off the weight")


@click.group()
def purchase() -> None:
    """Agreements to buy barley."""


@purchase.command("add")
@click.argument("code")
@click.argument("party")
@click.argument("variety")
@click.option("--tonnes", type=float, required=True)
@click.option("--price", type=str, required=True, help="per tonne.")
@click.option("--standard", "standard_name", type=str, required=True)
@click.option("--crop", type=int, required=True, help="the crop year.")
@click.option("--from", "opens", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@click.option("--to", "closes", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@pass_context
def purchase_add(
    context: Context,
    code: str,
    party: str,
    variety: str,
    tonnes: float,
    price: str,
    standard_name: str,
    crop: int,
    opens: dt.datetime,
    closes: dt.datetime,
) -> None:
    """Write a purchase."""
    written = add_purchase(
        context.book(),
        Purchase(
            code=code,
            party=party,
            variety=variety,
            crop_year=crop,
            tonnes=tonnes,
            window=Window(opens.date(), closes.date()),
            standard=standard_name,
            price_per_tonne=Decimal(price),
            signed=context.on,
        ),
    )
    click.echo(f"{written.code} added, {written.tonnes:.0f}t worth {written.value}.")


@purchase.command("extend")
@click.argument("code")
@click.argument("until", type=click.DateTime(formats=["%Y-%m-%d"]))
@pass_context
def purchase_extend(context: Context, code: str, until: dt.datetime) -> None:
    """Push a delivery window out to a later day."""
    moved = extend_window(context.book(), code, until.date())
    click.echo(f"{code} now runs {moved.window}.")


@purchase.command("list")
@click.option("--party", default=None)
@click.option("--crop", type=int, default=None)
@pass_context
def purchase_list(context: Context, party: str | None, crop: int | None) -> None:
    """List the purchases and what is left on each."""
    echo_lines(
        table(
            [
                Column("code"),
                Column("grower"),
                Column("variety"),
                Column("crop", Align.RIGHT),
                Column("tonnes", Align.RIGHT),
                Column("settled", Align.RIGHT),
                Column("left", Align.RIGHT),
                Column("window"),
            ],
            [
                [
                    item.code,
                    item.party,
                    item.variety,
                    str(item.crop_year),
                    f"{item.tonnes:.0f}",
                    f"{settled_against(context.book(), item.code):.1f}",
                    f"{outstanding(context.book(), item.code):.1f}",
                    str(item.window),
                ]
                for item in list_purchases(context.book(), party=party, crop_year=crop)
            ],
        )
    )


@purchase.command("show")
@click.argument("code")
@pass_context
def purchase_show(context: Context, code: str) -> None:
    """Say everything about one purchase."""
    found = get_purchase(context.book(), code)
    click.echo(f"{found.code}")
    click.echo(f"grower    {found.party}")
    click.echo(f"variety   {found.variety} crop {found.crop_year}")
    click.echo(f"standard  {found.standard}")
    click.echo(f"tonnes    {found.tonnes:.0f} at {found.price_per_tonne} = {found.value}")
    click.echo(f"window    {found.window}")
    click.echo(f"settled   {settled_against(context.book(), code):.2f}")
    click.echo(f"left      {outstanding(context.book(), code):.2f}")


@click.group()
def delivery() -> None:
    """Lorry loads of barley."""


@delivery.command("add")
@click.argument("ticket")
@click.argument("purchase_code")
@click.option("--party", required=True)
@click.option("--gross", type=float, required=True, help="kilogrammes.")
@click.option("--tare", type=float, required=True, help="kilogrammes.")
@click.option("--haulier", default=None)
@click.option("--vehicle", default=None)
@click.option("--harvested", type=click.DateTime(formats=["%Y-%m-%d"]), default=None)
@pass_context
def delivery_add(
    context: Context,
    ticket: str,
    purchase_code: str,
    party: str,
    gross: float,
    tare: float,
    haulier: str | None,
    vehicle: str | None,
    harvested: dt.datetime | None,
) -> None:
    """Take a lorry in against a purchase."""
    written = weigh_in(
        context.book(),
        Delivery(
            ticket=ticket,
            purchase=purchase_code,
            party=party,
            arrived=context.on,
            gross_kg=gross,
            tare_kg=tare,
            haulier=haulier,
            vehicle=vehicle,
            harvested=None if harvested is None else harvested.date(),
        ),
    )
    click.echo(f"{written} taken in.")


@delivery.command("harvest")
@click.argument("ticket")
@click.argument("cut", type=click.DateTime(formats=["%Y-%m-%d"]))
@pass_context
def delivery_harvest(context: Context, ticket: str, cut: dt.datetime) -> None:
    """Say when the barley on a load was cut, which the screen needs."""
    record_harvest(context.book(), ticket, cut.date())
    click.echo(f"{ticket} was cut on {cut.date()}.")


@delivery.command("sample")
@click.argument("ticket")
@click.argument("reference")
@click.option("--result", "results", multiple=True, help="code=value, repeatable.")
@click.option("--note", default="")
@pass_context
def delivery_sample(
    context: Context, ticket: str, reference: str, results: tuple[str, ...], note: str
) -> None:
    """Put a barley analysis against a load."""
    analysis = analysis_of(
        reference, Material.BARLEY, context.on, parse_results(results, Material.BARLEY)
    )
    take_sample(context.book(), ticket, analysis, note)
    click.echo(f"{ticket} sampled as {reference}, {len(analysis)} determinations.")


@delivery.command("grade")
@click.argument("ticket")
@click.option(
    "--finding",
    "findings",
    multiple=True,
    type=click.Choice(
        [
            RejectionReason.INSECT.value,
            RejectionReason.ODOUR.value,
            RejectionReason.TREATED_SEED.value,
        ]
    ),
    help="something somebody saw, which rejects whatever the numbers say.",
)
@pass_context
def delivery_grade(context: Context, ticket: str, findings: tuple[str, ...]) -> None:
    """Screen and grade a sampled load."""
    grading = grade_load(
        context.book(),
        ticket,
        context.on,
        findings=frozenset(RejectionReason(item) for item in findings),
    )
    if grading.rejected:
        reasons = ", ".join(str(reason) for reason in grading.rejections)
        click.echo(f"{ticket} REJECTED: {reasons}")
        return
    click.echo(f"{ticket} {grading.outcome}, {grading.settled_tonnes:.3f}t settled.")
    for line in grading.adjustments:
        click.echo(f"  {line}")


@delivery.command("settle")
@click.argument("ticket")
@pass_context
def delivery_settle(context: Context, ticket: str) -> None:
    """Say what a graded load is worth."""
    settlement = settle_load(context.book(), ticket)
    if settlement is None:
        grading = get_grading(context.book(), ticket)
        reasons = ", ".join(str(reason) for reason in grading.rejections)
        click.echo(f"{ticket} was rejected for {reasons}, so there is nothing to settle.")
        return
    click.echo(f"{settlement}")


@delivery.command("waiting")
@pass_context
def delivery_waiting(context: Context) -> None:
    """Every load that cannot move on, and what it is waiting for."""
    rows = []
    for item in unsampled(context.book(), until=context.on):
        rows.append([item.ticket, item.party, item.arrived.isoformat(), "sample"])
    for ticket in ungraded(context.book(), until=context.on):
        item = get_delivery(context.book(), ticket)
        rows.append([ticket, item.party, item.arrived.isoformat(), "grading"])
    echo_lines(
        table(
            [Column("ticket"), Column("grower"), Column("arrived"), Column("waiting for")],
            sorted(rows),
        )
    )


@delivery.command("list")
@click.option("--party", default=None)
@click.option("--purchase", "purchase_code", default=None)
@pass_context
def delivery_list(context: Context, party: str | None, purchase_code: str | None) -> None:
    """List the lorries."""
    echo_lines(
        table(
            [
                Column("ticket"),
                Column("grower"),
                Column("arrived"),
                Column("net", Align.RIGHT),
                Column("sampled"),
            ],
            [
                [
                    item.ticket,
                    item.party,
                    item.arrived.isoformat(),
                    f"{item.net_tonnes:.2f}",
                    item.sample or "",
                ]
                for item in list_deliveries(context.book(), party=party, purchase=purchase_code)
            ],
        )
    )
