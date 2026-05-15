"""Commands for the laboratory and the malt store: specifications, bins, lots.

The blend command is the one worth reading. It works out what a set of lots
would assay if they were run together, on the right weighting for each
determination, and says whether the answer meets a specification. Nobody
should be doing that on a spreadsheet, and everybody does.
"""

from __future__ import annotations

from pathlib import Path

import click

from culmbin.blend.plan import Part, assess, common_codes, plan_of, predict
from culmbin.cli.context import Context, echo_lines, pass_context
from culmbin.cli.values import parse_clause, parse_draw, parse_results
from culmbin.model.analytes import analyte, report
from culmbin.model.enums import BinState, Conformance, Material
from culmbin.model.lots import Bin
from culmbin.model.results import analysis_of
from culmbin.model.spec import Specification
from culmbin.report.layout import Align, Column, table
from culmbin.report.stock import bin_page, laboratory_page, stock_page
from culmbin.sales.certificate import write
from culmbin.store.analyses import get_analysis, save_analysis
from culmbin.store.bins import add_bin, clean_out, contents_of, issue, list_bins, receive, seal
from culmbin.store.loading import load
from culmbin.store.lots import certify, get_lot, list_lots, seal_lot
from culmbin.store.specs import (
    copy_specification,
    get_specification,
    list_specifications,
    save_specification,
)

CONFORMANCE_WORDS = {
    Conformance.PASS: "meets",
    Conformance.FAIL: "does NOT meet",
    Conformance.UNTESTED: "has not been fully tested against",
}


@click.group()
def spec() -> None:
    """The specifications customers sign against."""


@spec.command("add")
@click.argument("name")
@click.option("--clause", "clauses", multiple=True, required=True, help="colour<=4.5, repeatable.")
@click.option(
    "--variety",
    "varieties",
    multiple=True,
    help="a variety the specification names, repeatable.",
)
@click.option(
    "--material",
    type=click.Choice([item.value for item in Material]),
    default=Material.MALT.value,
    help="what the specification is about.",
)
@pass_context
def spec_add(
    context: Context,
    name: str,
    clauses: tuple[str, ...],
    varieties: tuple[str, ...],
    material: str,
) -> None:
    """Write a specification."""
    written = Specification(
        name=name,
        material=Material(material),
        clauses=tuple(parse_clause(clause) for clause in clauses),
        varieties=frozenset(varieties),
    )
    save_specification(context.book(), written)
    click.echo(f"{name} added, {len(written)} clauses.")


@spec.command("copy")
@click.argument("name")
@click.argument("into")
@pass_context
def spec_copy(context: Context, name: str, into: str) -> None:
    """Start next season's specification off this one."""
    copy_specification(context.book(), name, into)
    click.echo(f"{into} copied from {name}.")


@spec.command("list")
@pass_context
def spec_list(context: Context) -> None:
    """List the specifications."""
    echo_lines(
        table(
            [
                Column("name"),
                Column("material"),
                Column("clauses", Align.RIGHT),
                Column("varieties"),
            ],
            [
                [item.name, str(item.material), str(len(item)), ", ".join(sorted(item.varieties))]
                for item in list_specifications(context.book())
            ],
        )
    )


@spec.command("show")
@click.argument("name")
@pass_context
def spec_show(context: Context, name: str) -> None:
    """Print one specification, in the order the customer wrote it."""
    found = get_specification(context.book(), name)
    click.echo(f"{found.name} ({found.material})")
    for clause in found:
        basis = "" if clause.basis is None else f" {clause.basis}"
        click.echo(f"  {clause}{basis}")
    if found.varieties:
        click.echo(f"  varieties: {', '.join(sorted(found.varieties))}")


@click.group("bin")
def malt_bin() -> None:
    """The bins finished malt is kept in."""


@malt_bin.command("add")
@click.argument("code")
@click.option("--capacity", type=float, required=True, help="tonnes.")
@pass_context
def bin_add(context: Context, code: str, capacity: float) -> None:
    """Put a bin in the register."""
    add_bin(context.book(), Bin(code, capacity, commissioned=context.on))
    click.echo(f"{code} added, holding {capacity:.0f}t.")


@malt_bin.command("receive")
@click.argument("code")
@click.argument("piece")
@click.option("--tonnes", type=float, required=True)
@click.option("--moisture", type=float, required=True)
@pass_context
def bin_receive(context: Context, code: str, piece: str, tonnes: float, moisture: float) -> None:
    """Tip a piece of malt into a bin.

    A second variety marks the bin mixed, and the mark stays until somebody
    has cleaned the bin out with a shovel.
    """
    after = receive(context.book(), code, piece, tonnes, moisture, context.on)
    held = contents_of(context.book(), code)
    context.note("binned", code, f"{tonnes:.2f}t of {piece}")
    click.echo(f"{code} holds {held.tonnes:.2f}t at {held.moisture:.2f}%.")
    if after.mixed:
        click.echo(f"{code} is now MIXED and no lot off it can declare a variety.")


@malt_bin.command("issue")
@click.argument("code")
@click.option("--tonnes", type=float, required=True)
@click.option("--note", default="", help="where the malt went.")
@pass_context
def bin_issue(context: Context, code: str, tonnes: float, note: str) -> None:
    """Draw malt out of a bin."""
    issue(context.book(), code, tonnes, context.on, note)
    held = contents_of(context.book(), code)
    click.echo(f"{code} holds {held.tonnes:.2f}t.")


@malt_bin.command("seal")
@click.argument("code")
@pass_context
def bin_seal(context: Context, code: str) -> None:
    """Seal a bin so a lot can be taken off it."""
    seal(context.book(), code)
    context.note("sealed", code)
    click.echo(f"{code} sealed.")


@malt_bin.command("clean")
@click.argument("code")
@pass_context
def bin_clean(context: Context, code: str) -> None:
    """Take the mixed mark off a bin that has been emptied and swept."""
    clean_out(context.book(), code)
    click.echo(f"{code} cleaned out, segregation mark cleared.")


@malt_bin.command("list")
@click.option(
    "--state",
    type=click.Choice([item.value for item in BinState]),
    default=None,
    help="only bins in this state.",
)
@pass_context
def bin_list(context: Context, state: str | None) -> None:
    """List the bins, or print the bin page when no state is asked for."""
    if state is None:
        click.echo(bin_page(context.book()), nl=False)
        return
    echo_lines(
        table(
            [Column("bin"), Column("state"), Column("holds", Align.RIGHT), Column("mixed")],
            [
                [
                    item.code,
                    str(item.state),
                    f"{contents_of(context.book(), item.code).tonnes:.2f}",
                    "MIXED" if item.mixed else "",
                ]
                for item in list_bins(context.book(), BinState(state))
            ],
        )
    )


@click.group()
def lot() -> None:
    """Sealed parcels of malt."""


@lot.command("seal")
@click.argument("code")
@click.option("--bin", "malt_bin_code", required=True)
@pass_context
def lot_seal(context: Context, code: str, malt_bin_code: str) -> None:
    """Take a lot off a sealed bin."""
    sealed = seal_lot(context.book(), code, malt_bin_code, context.on)
    variety = sealed.variety or "no variety, the bin is mixed"
    context.note("lotted", code, f"{sealed.tonnes:.2f}t off {malt_bin_code}")
    click.echo(f"{sealed.code} sealed, {sealed.tonnes:.2f}t, {variety}.")


@lot.command("certify")
@click.argument("code")
@click.argument("reference")
@click.option("--result", "results", multiple=True, required=True, help="code=value, repeatable.")
@click.option("--note", default="", help="anything the laboratory wrote alongside.")
@pass_context
def lot_certify(
    context: Context, code: str, reference: str, results: tuple[str, ...], note: str
) -> None:
    """Put a malt analysis against a lot."""
    analysis = analysis_of(
        reference, Material.MALT, context.on, parse_results(results, Material.MALT)
    )
    save_analysis(context.book(), analysis, note)
    certify(context.book(), code, reference)
    context.note("certified", code, reference)
    click.echo(f"{code} certified as {reference}, {len(analysis)} determinations.")


@lot.command("show")
@click.argument("code")
@click.option("--against", "specification", default=None, help="assess against a specification.")
@pass_context
def lot_show(context: Context, code: str, specification: str | None) -> None:
    """Print the certificate of analysis for a lot."""
    click.echo(write(context.book(), code, context.on, specification), nl=False)


@lot.command("list")
@click.option("--variety", default=None, help="lots that can be SOLD as this variety.")
@click.option("--uncertified", is_flag=True, help="only the ones the laboratory still owes.")
@pass_context
def lot_list(context: Context, variety: str | None, uncertified: bool) -> None:
    """List the lots, or print the stock page when nothing is asked for."""
    if variety is None and not uncertified:
        click.echo(stock_page(context.book()), nl=False)
        return
    if uncertified:
        click.echo(laboratory_page(context.book()), nl=False)
        return
    echo_lines(
        table(
            [Column("lot"), Column("bin"), Column("tonnes", Align.RIGHT), Column("variety")],
            [
                [item.code, item.bin_code, f"{item.tonnes:.2f}", item.variety or "mixed"]
                for item in list_lots(context.book(), variety=variety)
            ],
        )
    )


@lot.command("load")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--note", default="", help="anything the laboratory wrote alongside.")
@pass_context
def lot_load(context: Context, path: Path, note: str) -> None:
    """Load a batch of laboratory results out of a file.

    The file loads whole or not at all. Eighty percent of a file is the
    worst possible outcome, because nobody can tell which twenty percent
    failed without reading the whole thing.
    """
    analyses = load(context.book(), path, note)
    click.echo(f"{len(analyses)} analyses loaded out of {path.name}.")
    for analysis in analyses:
        click.echo(f"  {analysis.reference:<16}{len(analysis)} determinations")
    context.note("loaded results", path.name, f"{len(analyses)} analyses")


@click.command()
@click.option("--draw", "draws", multiple=True, required=True, help="LOT:TONNES, repeatable.")
@click.option("--against", "specification", default=None, help="assess the blend against this.")
@pass_context
def blend(context: Context, draws: tuple[str, ...], specification: str | None) -> None:
    """Say what a set of lots would assay if they were run together.

    Extract averages over dry matter, colour over the weight as it lies, and
    the Kolbach index does not average at all. Doing that by hand is how a
    blend lands a tenth of a percent out and nobody notices.
    """
    book = context.book()
    parts = []
    for draw in draws:
        code, tonnes = parse_draw(draw)
        held = get_lot(book, code)
        if held.analysis is None:
            raise click.ClickException(f"{code} has no analysis, so it cannot be blended")
        parts.append(Part(lot=held, tonnes=tonnes, analysis=get_analysis(book, held.analysis)))
    plan = plan_of("blend", parts)
    predicted = predict(plan, "predicted", context.on)
    click.echo(f"{plan.tonnes:.2f}t, {plan.dry_tonnes:.2f}t dry, {plan.variety or 'mixed'}")
    for code in sorted(common_codes(plan)):
        item = analyte(code)
        value = report(code, predicted.value_on(code, item.basis))
        click.echo(f"  {item.label:<22}{value} {item.unit}")
    if specification is not None:
        assessment = assess(plan, get_specification(book, specification), "predicted", context.on)
        click.echo(f"this blend {CONFORMANCE_WORDS[assessment.conformance]} {specification}.")
        for outcome in assessment.failures:
            click.echo(f"  {outcome.clause} but the blend is {outcome.value:.2f}")
