"""Writing the book out as CSV."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from culmbin.errors import ConflictError
from culmbin.store.book import Book
from culmbin.store.export import SKIP, export_book, exportable


def test_every_table_gets_a_file(stocked: Book, tmp_path: Path) -> None:
    written = export_book(stocked, tmp_path)
    assert len(written) == len(exportable(stocked))
    assert (tmp_path / "party.csv").exists()


def test_the_version_table_is_left_out(stocked: Book, tmp_path: Path) -> None:
    """It describes the book rather than what is in it."""
    export_book(stocked, tmp_path)
    assert not (tmp_path / "schema_version.csv").exists()
    assert frozenset({"schema_version"}) == SKIP


def test_the_file_has_a_heading_row(stocked: Book, tmp_path: Path) -> None:
    export_book(stocked, tmp_path)
    with (tmp_path / "party.csv").open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == list(stocked.columns("party"))
    assert len(rows) == 5


def test_an_empty_table_still_gets_a_file(stocked: Book, tmp_path: Path) -> None:
    export_book(stocked, tmp_path)
    with (tmp_path / "shipment.csv").open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 1


def test_the_table_list_comes_off_the_book(stocked: Book) -> None:
    """A table added by a migration and not by hand is still exported."""
    assert set(exportable(stocked)) == set(stocked.tables()) - SKIP


def test_exporting_over_an_older_export_is_refused(stocked: Book, tmp_path: Path) -> None:
    export_book(stocked, tmp_path)
    with pytest.raises(ConflictError, match="already holds"):
        export_book(stocked, tmp_path)


def test_a_directory_that_is_not_there_yet_is_made(stocked: Book, tmp_path: Path) -> None:
    into = tmp_path / "one" / "two"
    export_book(stocked, into)
    assert into.is_dir()
