"""Commands for the plant: the recipes, and a piece from charge to strip."""

from __future__ import annotations

import click

from culmbin.cli.context import Context, echo_lines, pass_context
from culmbin.cli.values import parse_leg, parse_step
from culmbin.model.enums import MaltStyle, PieceStage
from culmbin.model.process import Piece
from culmbin.process.floor import balance_of, cast, charge, load_kiln, strip_kiln
from culmbin.process.germination import Schedule
from culmbin.process.kiln import Curve, predicted_colour
from culmbin.process.steep import Programme, predicted_steep_out
from culmbin.report.layout import Align, Column, table
from culmbin.report.process import piece_page
from culmbin.store.pieces import add_reading, list_pieces, record_source, write_off_piece
from culmbin.store.recipes import (
    get_curve,
    get_programme,
    get_schedule,
    list_curves,
    list_programmes,
    list_schedules,
    save_curve,
    save_programme,
    save_schedule,
)
from culmbin.units.clock import Leg

STYLES = [item.value for item in MaltStyle]
READING_STAGES = [
    PieceStage.STEEPING.value,
    PieceStage.GERMINATING.value,
    PieceStage.KILNING.value,
]


@click.group()
def recipe() -> None:
    """Steep programmes, germination schedules and kiln curves."""


@recipe.command("programme")
@click.argument("name")
@click.option("--style", type=click.Choice(STYLES), required=True)
@click.option("--leg", "legs", multiple=True, required=True, help="wet:8:14, repeatable.")
@click.option("--target", type=float, required=True, help="steep-out moisture.")
@pass_context
def recipe_programme(
    context: Context, name: str, legs: tuple[str, ...], style: str, target: float
) -> None:
    """Write a steep programme.

    The legs alternate. Two wet stands together is one long wet stand
    written down badly, and it is refused.
    """
    programme = Programme(name, MaltStyle(style), tuple(parse_leg(leg) for leg in legs), target)
    save_programme(context.book(), programme)
    click.echo(
        f"{name} added, {programme.stands} stands over {programme.total_hours:.0f}h, "
        f"expecting {predicted_steep_out(programme, 12.0):.1f}% off 12% barley."
    )


@recipe.command("schedule")
@click.argument("name")
@click.option("--style", type=click.Choice(STYLES), required=True)
@click.option("--target", type=float, required=True, help="degree hours to cast off.")
@click.option("--turn", "turns", multiple=True, type=float, help="degree hours, repeatable.")
@pass_context
def recipe_schedule(
    context: Context, name: str, style: str, target: float, turns: tuple[float, ...]
) -> None:
    """Write a germination schedule.

    The turning points are degree hours, not hours, so a cold box gets fewer
    turns over the same number of days rather than more.
    """
    schedule = Schedule(name, MaltStyle(style), target, tuple(sorted(turns)))
    save_schedule(context.book(), schedule)
    click.echo(
        f"{name} added, {schedule.turns} turns, about {schedule.days_at(16.0):.1f} days at 16C."
    )


@recipe.command("curve")
@click.argument("name")
@click.option("--style", type=click.Choice(STYLES), required=True)
@click.option("--step", "steps", multiple=True, required=True, help="dry:10:60, repeatable.")
@click.option("--target", type=float, required=True, help="off-kiln moisture.")
@pass_context
def recipe_curve(
    context: Context, name: str, style: str, steps: tuple[str, ...], target: float
) -> None:
    """Write a kiln curve."""
    curve = Curve(name, MaltStyle(style), tuple(parse_step(step) for step in steps), target)
    save_curve(context.book(), curve)
    click.echo(
        f"{name} added, {curve.hours:.0f}h to {curve.peak_c:.0f}C, "
        f"expecting {predicted_colour(curve, 44.0):.1f} EBC."
    )


@recipe.command("list")
@pass_context
def recipe_list(context: Context) -> None:
    """List all three kinds of recipe."""
    rows = [
        ["programme", item.name, str(item.style), f"{item.total_hours:.0f}h"]
        for item in list_programmes(context.book())
    ]
    rows += [
        ["schedule", item.name, str(item.style), f"{item.target_degree_hours:.0f} degree h"]
        for item in list_schedules(context.book())
    ]
    rows += [
        ["curve", item.name, str(item.style), f"{item.hours:.0f}h"]
        for item in list_curves(context.book())
    ]
    echo_lines(table([Column("kind"), Column("name"), Column("style"), Column("size")], rows))


@recipe.command("show")
@click.argument("kind", type=click.Choice(["programme", "schedule", "curve"]))
@click.argument("name")
@pass_context
def recipe_show(context: Context, kind: str, name: str) -> None:
    """Print the steps of one recipe in order."""
    book = context.book()
    if kind == "programme":
        programme = get_programme(book, name)
        click.echo(f"{programme.name} ({programme.style}) to {programme.target_moisture:.1f}%")
        for index, leg in enumerate(programme.legs, start=1):
            click.echo(f"  {index}. {leg}")
        return
    if kind == "schedule":
        schedule = get_schedule(book, name)
        click.echo(
            f"{schedule.name} ({schedule.style}) to {schedule.target_degree_hours:.0f} degree h"
        )
        for index, point in enumerate(schedule.turns_at, start=1):
            click.echo(f"  turn {index} at {point:.0f}")
        return
    curve = get_curve(book, name)
    click.echo(f"{curve.name} ({curve.style}) to {curve.target_moisture:.1f}%")
    for index, step in enumerate(curve.steps, start=1):
        click.echo(f"  {index}. {step}")


@click.group()
def piece() -> None:
    """Batches of malt, from the steep to the bin."""


@piece.command("charge")
@click.argument("code")
@click.option("--variety", required=True)
@click.option("--crop", type=int, required=True)
@click.option("--style", type=click.Choice(STYLES), required=True)
@click.option("--steep", required=True)
@click.option("--tonnes", type=float, required=True)
@click.option("--moisture", type=float, required=True)
@click.option("--programme", required=True)
@click.option("--schedule", required=True)
@click.option("--curve", required=True)
@click.option("--share", is_flag=True, help="allow a second piece in the same vessel.")
@pass_context
def piece_charge(
    context: Context,
    code: str,
    variety: str,
    crop: int,
    style: str,
    steep: str,
    tonnes: float,
    moisture: float,
    programme: str,
    schedule: str,
    curve: str,
    share: bool,
) -> None:
    """Put a charge of barley into a steep."""
    written = charge(
        context.book(),
        Piece(
            code=code,
            variety=variety,
            crop_year=crop,
            style=MaltStyle(style),
            charge_tonnes=tonnes,
            charge_moisture=moisture,
            started=context.on,
            stage=PieceStage.STEEPING,
            vessel=steep,
        ),
        programme,
        schedule,
        curve,
        share=share,
    )
    context.note("charged", code, f"{tonnes:.2f}t into {steep}")
    click.echo(f"{written} charged, {written.charge_dry_tonnes:.2f}t dry matter.")


@piece.command("source")
@click.argument("code")
@click.argument("ticket")
@click.option("--tonnes", type=float, required=True)
@pass_context
def piece_source(context: Context, code: str, ticket: str, tonnes: float) -> None:
    """Say which lorry load part of a charge came out of.

    Without this the backward walk stops at the steep, which is the wrong
    end of it: the question is always whose barley is in the beer.
    """
    record_source(context.book(), code, ticket, tonnes)
    click.echo(f"{code} carries {tonnes:.2f}t off {ticket}.")


@piece.command("reading")
@click.argument("code")
@click.option("--stage", type=click.Choice(READING_STAGES), required=True)
@click.option("--hours", type=float, required=True)
@click.option("--celsius", type=float, required=True)
@pass_context
def piece_reading(context: Context, code: str, stage: str, hours: float, celsius: float) -> None:
    """Record a stretch of time at a temperature against a piece."""
    add_reading(context.book(), code, PieceStage(stage), Leg(hours=hours, celsius=celsius))
    click.echo(f"{code} {stage}: {hours:g}h at {celsius:g}C.")


@piece.command("cast")
@click.argument("code")
@click.option("--into", required=True, help="the box or floor.")
@click.option("--tonnes", type=float, required=True, help="steep-out weight.")
@click.option("--moisture", type=float, required=True, help="steep-out moisture.")
@click.option("--depth", type=float, required=True, help="bed depth in centimetres.")
@click.option("--share", is_flag=True, help="allow a second piece in the same bed.")
@pass_context
def piece_cast(
    context: Context,
    code: str,
    into: str,
    tonnes: float,
    moisture: float,
    depth: float,
    share: bool,
) -> None:
    """Cast a piece out of the steep and into a bed."""
    moved = cast(context.book(), code, into, context.on, tonnes, moisture, depth, share=share)
    context.note("cast", code, f"into {into} at {depth:.0f}cm")
    click.echo(f"{moved} cast at {depth:.0f}cm.")


@piece.command("kiln")
@click.argument("code")
@click.option("--into", required=True)
@click.option("--share", is_flag=True, help="allow a second piece on the same kiln.")
@pass_context
def piece_kiln(context: Context, code: str, into: str, share: bool) -> None:
    """Move a piece off the floor and onto a kiln."""
    moved = load_kiln(context.book(), code, into, context.on, share=share)
    context.note("loaded", code, f"onto {into}")
    click.echo(f"{moved} loaded.")


@piece.command("strip")
@click.argument("code")
@click.option("--malt", type=float, required=True, help="tonnes off the kiln.")
@click.option("--moisture", type=float, required=True)
@click.option("--culm", type=float, required=True, help="tonnes of rootlet.")
@pass_context
def piece_strip(context: Context, code: str, malt: float, moisture: float, culm: float) -> None:
    """Take a piece off the kiln and weigh the malt and the culm."""
    strip_kiln(context.book(), code, context.on, malt, moisture, culm)
    balance = balance_of(context.book(), code)
    context.note("stripped", code, f"{malt:.2f}t at {moisture:.1f}%")
    click.echo(f"{code} stripped, {malt:.2f}t at {moisture:.1f}%.")
    click.echo(f"malting loss {balance.malting_loss:.2f}%, yield {balance.yield_percent:.2f}%.")


@piece.command("writeoff")
@click.argument("code")
@click.option("--note", required=True, help="why.")
@pass_context
def piece_writeoff(context: Context, code: str, note: str) -> None:
    """Write a piece off from wherever it had got to."""
    write_off_piece(context.book(), code, context.on, note)
    context.note("written off", code, note)
    click.echo(f"{code} written off: {note}")


@piece.command("show")
@click.argument("code")
@pass_context
def piece_show(context: Context, code: str) -> None:
    """The whole life of one piece."""
    click.echo(piece_page(context.book(), code), nl=False)


@piece.command("list")
@click.option(
    "--stage",
    type=click.Choice([item.value for item in PieceStage]),
    default=None,
    help="only pieces at this stage.",
)
@click.option("--variety", default=None, help="only pieces of this variety.")
@pass_context
def piece_list(context: Context, stage: str | None, variety: str | None) -> None:
    """List the pieces."""
    pieces = list_pieces(
        context.book(), stage=None if stage is None else PieceStage(stage), variety=variety
    )
    echo_lines(
        table(
            [
                Column("piece"),
                Column("variety"),
                Column("style"),
                Column("charge", Align.RIGHT),
                Column("stage"),
                Column("vessel"),
            ],
            [
                [
                    item.code,
                    item.variety,
                    str(item.style),
                    f"{item.charge_tonnes:.1f}",
                    str(item.stage),
                    item.vessel or "",
                ]
                for item in pieces
            ],
        )
    )
