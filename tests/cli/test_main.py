"""The console script itself."""

from __future__ import annotations

from pathlib import Path

from culmbin import __version__
from culmbin.store.book import Book
from culmbin.store.migrations import current_version, latest_version
from tests.cli.conftest import Invoke


def test_the_version_is_the_package_version(invoke: Invoke) -> None:
    result = invoke("--version")
    assert result.exit_code == 0
    assert __version__ in result.output


def test_init_makes_a_book_at_the_latest_version(invoke: Invoke, book_path: Path) -> None:
    result = invoke("init")
    assert result.exit_code == 0
    assert book_path.exists()
    with Book.open(book_path) as book:
        assert current_version(book) == latest_version()


def test_init_lists_what_it_applied(invoke: Invoke) -> None:
    result = invoke("init")
    assert "parties, varieties and vessels" in result.output
    assert f"version {latest_version()}" in result.output


def test_init_twice_says_there_was_nothing_to_do(invoke: Invoke) -> None:
    invoke("init")
    result = invoke("init")
    assert result.exit_code == 0
    assert "already at version" in result.output


def test_status_says_where_the_book_is_and_what_day_it_is(invoke: Invoke) -> None:
    invoke("init")
    result = invoke("status", on="2025-11-04")
    assert result.exit_code == 0
    assert "as at     2025-11-04" in result.output
    assert f"schema    {latest_version()} of {latest_version()}" in result.output


def test_status_opens_a_book_that_is_not_there_yet(invoke: Invoke) -> None:
    """Every command migrates, so the first one anybody runs works."""
    result = invoke("status")
    assert result.exit_code == 0
    assert "schema" in result.output


def test_status_counts_only_tables_with_something_in_them(invoke: Invoke) -> None:
    invoke("init")
    result = invoke("status")
    assert "schema_version" in result.output
    assert "party" not in result.output


def test_backup_copies_the_book(invoke: Invoke, tmp_path: Path) -> None:
    invoke("init")
    target = tmp_path / "copy.sqlite3"
    result = invoke("backup", str(target))
    assert result.exit_code == 0
    assert target.exists()
    with Book.open(target) as copy:
        assert current_version(copy) == latest_version()


def test_a_command_that_is_not_one_is_a_usage_error(invoke: Invoke) -> None:
    result = invoke("nonsense")
    assert result.exit_code == 2


def test_a_date_that_is_not_one_is_a_usage_error(invoke: Invoke) -> None:
    result = invoke("status", on="the fourth")
    assert result.exit_code == 2


def test_the_help_says_what_the_package_is(invoke: Invoke) -> None:
    result = invoke("--help")
    assert "malthouse" in result.output


def test_every_command_is_in_the_help(invoke: Invoke) -> None:
    result = invoke("--help")
    for command in ("init", "status", "backup"):
        assert command in result.output
