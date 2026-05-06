"""What every command is given."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click
import pytest

from culmbin.cli.context import DEFAULT_BOOK, Context, echo_lines
from culmbin.store.migrations import current_version, latest_version

TODAY = dt.date(2025, 11, 4)


def test_the_book_is_opened_and_migrated_once(tmp_path: Path) -> None:
    context = Context(path=str(tmp_path / "book.sqlite3"), on=TODAY)
    book = context.book()
    assert current_version(book) == latest_version()
    assert context.book() is book
    context.close()


def test_closing_twice_is_not_an_error(tmp_path: Path) -> None:
    context = Context(path=str(tmp_path / "book.sqlite3"), on=TODAY)
    context.book()
    context.close()
    context.close()


def test_closing_a_context_that_never_opened_one_is_fine(tmp_path: Path) -> None:
    Context(path=str(tmp_path / "book.sqlite3"), on=TODAY).close()


def test_the_stamp_is_the_day_a_migration_records(tmp_path: Path) -> None:
    context = Context(path=str(tmp_path / "book.sqlite3"), on=TODAY)
    assert context.stamp == "2025-11-04T00:00:00+00:00"


def test_the_default_book_is_in_the_working_directory() -> None:
    assert DEFAULT_BOOK == "culmbin.sqlite3"


def test_echo_lines_prints_a_block(capsys: pytest.CaptureFixture[str]) -> None:
    with click.Context(click.Command("x")):
        echo_lines(["one", "two"])
    assert capsys.readouterr().out == "one\ntwo\n"


def test_echo_lines_of_nothing_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    with click.Context(click.Command("x")):
        echo_lines([])
    assert capsys.readouterr().out == ""


def test_a_book_can_be_opened_without_migrating_it(tmp_path: Path) -> None:
    """Migrating first and then reporting nothing to apply is true and useless."""
    context = Context(path=str(tmp_path / "book.sqlite3"), on=TODAY)
    book = context.book_as_is()
    assert current_version(book) == 0
    context.close()


def test_opening_as_is_keeps_the_same_book(tmp_path: Path) -> None:
    context = Context(path=str(tmp_path / "book.sqlite3"), on=TODAY)
    assert context.book_as_is() is context.book_as_is()
    context.close()
