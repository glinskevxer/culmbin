"""Commands over the journal: what was done, by whom, and to what."""

from __future__ import annotations

import datetime as dt

import click

from culmbin.cli.context import Context, echo_lines, pass_context
from culmbin.cli.window import window_for, window_options
from culmbin.store.journal import about, actors, entries, unattributed


@click.group()
def journal() -> None:
    """What was done to the book, by whom, and when."""


@journal.command("show")
@click.argument("subject")
@pass_context
def journal_show(context: Context, subject: str) -> None:
    """Everything ever done to one thing, oldest first."""
    found = about(context.book(), subject)
    if not found:
        click.echo(f"nothing has been done to {subject}.")
        return
    echo_lines([str(entry) for entry in found])


@journal.command("list")
@click.option("--by", "actor", default=None, help="only what one person did.")
@window_options
@pass_context
def journal_list(
    context: Context, actor: str | None, opens: dt.datetime | None, closes: dt.datetime | None
) -> None:
    """Everything done over a stretch of days."""
    window = window_for(context, opens, closes)
    found = entries(context.book(), actor=actor, since=window.start, until=window.end)
    if not found:
        click.echo("nothing was done.")
        return
    echo_lines([str(entry) for entry in found])


@journal.command("who")
@pass_context
def journal_who(context: Context) -> None:
    """Everybody who has done anything, and how much is unattributed."""
    for actor in actors(context.book()):
        click.echo(actor)
    missing = unattributed(context.book())
    if missing:
        click.echo(f"{missing} entries have nobody against them.")
