"""The schema document is generated from the migrations."""

from __future__ import annotations

from pathlib import Path

import pytest

from culmbin.store.migrations import MIGRATIONS, latest_version
from culmbin.tools import schema_dump


def test_the_document_on_disk_is_current() -> None:
    assert schema_dump.main(["--check"]) == 0


def test_the_document_names_every_migration() -> None:
    text = schema_dump.render()
    for migration in MIGRATIONS:
        assert migration.name in text


def test_the_document_says_the_schema_version() -> None:
    assert f"Schema version {latest_version()}" in schema_dump.render()


def test_the_document_has_a_block_for_every_table() -> None:
    text = schema_dump.render()
    for table in ("party", "delivery", "malt_lot", "shipment", "piece_source"):
        assert f"## {table}" in text


def test_a_foreign_key_is_written_down() -> None:
    assert "`purchase` refers to `purchase.code`" in schema_dump.render()


def test_an_index_is_written_down() -> None:
    assert "index `delivery_by_day`" in schema_dump.render()


def test_a_unique_index_says_it_is_unique() -> None:
    assert "unique index `clause_once_per_analyte`" in schema_dump.render()


def test_generating_writes_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "schema.md"
    monkeypatch.setattr(schema_dump, "document_path", lambda: target)
    assert schema_dump.main([]) == 0
    assert target.read_text(encoding="utf-8") == schema_dump.render()


def test_a_stale_document_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "schema.md"
    target.write_text("# something else\n", encoding="utf-8")
    monkeypatch.setattr(schema_dump, "document_path", lambda: target)
    assert schema_dump.main(["--check"]) == 1


def test_a_missing_document_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schema_dump, "document_path", lambda: tmp_path / "nothing.md")
    assert schema_dump.main(["--check"]) == 1


def test_the_document_ends_in_one_newline() -> None:
    text = schema_dump.render()
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
