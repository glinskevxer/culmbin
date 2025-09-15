"""The console script: options, the book, and what an error turns into.

The clock lives here. Everything below takes the day as an argument, which
is why the rules can be tested without freezing time and why a report for
last Tuesday is the same code as a report for today.

Exit statuses:

- 0, it worked
- 1, one of ours went wrong and the message says which
- 2, the command line was not usable, which is click's

An unexpected exception is not caught. A traceback out of this package is a
bug and hiding it behind a tidy message is how it stays one.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import click

from culmbin import __version__
from culmbin.cli.context import DEFAULT_BOOK, Context, pass_context
from culmbin.cli.intake import delivery, purchase, standard
from culmbin.cli.process import piece, recipe
from culmbin.cli.registers import party, variety, vessel
from culmbin.errors import CulmbinError
from culmbin.store.book import Book
from culmbin.store.migrations import current_version, latest_version, migrate, pending


@click.group()
@click.version_option(version=__version__, prog_name="culmbin")
@click.option(
    "--book",
    "book_path",
    default=DEFAULT_BOOK,
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="the SQLite file to work in.",
)
@click.option(
    "--on",
    "on",
    default=None,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="the day to work as, for reports and records. Defaults to today.",
)
@click.pass_context
def cli(context: click.Context, book_path: Path, on: dt.datetime | None) -> None:
    """Record keeping for a malthouse."""
    day = dt.date.today() if on is None else on.date()  # noqa: DTZ011
    context.obj = Context(path=str(book_path), on=day)
    context.call_on_close(context.obj.close)


@cli.command()
@pass_context
def init(context: Context) -> None:
    """Make a book, or bring an existing one up to date."""
    book = Book.open(context.path)
    try:
        before = current_version(book)
        applied = migrate(book, context.stamp)
    finally:
        book.close()
    if not applied:
        click.echo(f"{context.path} is already at version {before}.")
        return
    for migration in applied:
        click.echo(f"{migration.version:3d}  {migration.name}")
    click.echo(f"{context.path} is at version {latest_version()}.")


@cli.command()
@pass_context
def status(context: Context) -> None:
    """Say what the book is and what is in it."""
    book = context.book()
    click.echo(f"book      {context.path}")
    click.echo(f"as at     {context.on.isoformat()}")
    click.echo(f"schema    {current_version(book)} of {latest_version()}")
    behind = pending(book)
    if behind:
        click.echo(f"pending   {len(behind)} migrations")
    for table in book.tables():
        count = book.scalar(f'SELECT count(*) FROM "{table}"')
        if count:
            click.echo(f"{table:<24}{count:>8}")


@cli.command()
@click.argument("target", type=click.Path(dir_okay=False, path_type=Path))
@pass_context
def backup(context: Context, target: Path) -> None:
    """Copy the book through SQLite rather than through the filesystem.

    Copying the file while anything is writing gives a copy that is a valid
    file and the wrong contents.
    """
    context.book().backup_to(target)
    click.echo(f"copied {context.path} to {target}")


cli.add_command(delivery)
cli.add_command(party)
cli.add_command(piece)
cli.add_command(recipe)
cli.add_command(purchase)
cli.add_command(standard)
cli.add_command(variety)
cli.add_command(vessel)


def run() -> int:
    """Run the console script, turning our own errors into an exit status."""
    try:
        cli.main(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.Abort:
        click.echo("aborted.", err=True)
        return 1
    except CulmbinError as exc:
        click.echo(f"culmbin: {exc}", err=True)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run())
