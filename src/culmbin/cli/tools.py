"""The two commands that are about the book rather than about malt."""

from __future__ import annotations

from pathlib import Path

import click

from culmbin import __version__
from culmbin.cli.context import Context, pass_context
from culmbin.report.book import book_page
from culmbin.store.export import export_book, exportable
from culmbin.store.integrity import faults, worth_a_look
from culmbin.store.migrations import MIGRATIONS, current_version, latest_version, pending
from culmbin.store.search import counts, search


@click.command()
@click.argument("code")
@pass_context
def find(context: Context, code: str) -> None:
    """Say what a code is, whatever kind of thing it turns out to be.

    Somebody has a number off a piece of paper. They should not have to know
    whether it is a lot, a ticket, a piece or a contract before they can ask.
    """
    found = search(context.book(), code)
    if not found:
        click.echo(f"nothing in the book is called {code!r}.")
        return
    for item in found:
        click.echo(str(item))


@click.command()
@click.argument("into", type=click.Path(file_okay=False, path_type=Path))
@pass_context
def export(context: Context, into: Path) -> None:
    """Write the whole book out as CSV, one file per table."""
    written = export_book(context.book(), into)
    click.echo(f"wrote {len(written)} files into {into}.")


@click.command()
@pass_context
def registers(context: Context) -> None:
    """Count every register the search looks in."""
    for kind, total in counts(context.book()):
        click.echo(f"{kind:<16}{total:>8}")
    click.echo(f"{len(exportable(context.book()))} tables would be exported.")


@click.command()
@click.option("--quiet", is_flag=True, help="say only whether anything is wrong.")
@pass_context
def doctor(context: Context, quiet: bool) -> None:
    """Ask the book whether it still makes sense.

    Exits non-zero when something is actually wrong, so it can be put in a
    cron job. Things that are merely odd do not fail it.
    """
    book = context.book()
    wrong = faults(book)
    if quiet:
        odd = worth_a_look(book)
        click.echo(f"{len(wrong)} wrong, {len(odd)} worth a look.")
    else:
        click.echo(book_page(book), nl=False)
    if wrong:
        raise SystemExit(1)


@click.command()
@pass_context
def version(context: Context) -> None:
    """Say what this is, what the book is, and what is between them.

    `--version` says the package version and stops. This says the package
    version, the book's schema version, and every migration the book has not
    had, which is the thing somebody actually wants before an upgrade.
    """
    click.echo(f"culmbin    {__version__}")
    click.echo(f"schema     {latest_version()} in this package")
    book = context.book_as_is()
    at = current_version(book)
    click.echo(f"book       {at} at {context.path}")
    behind = pending(book)
    if not behind:
        click.echo("the book is up to date.")
        return
    click.echo(f"{len(behind)} migrations would be applied:")
    for migration in behind:
        click.echo(f"  {migration.version:3d}  {migration.name}")


@click.command()
@pass_context
def migrations(context: Context) -> None:
    """Every migration this package knows about, and whether the book has it."""
    book = context.book_as_is()
    at = current_version(book)
    for migration in MIGRATIONS:
        mark = "applied" if migration.version <= at else "waiting"
        click.echo(f"{migration.version:3d}  {mark}  {migration.name}")
