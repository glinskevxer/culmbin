"""A migration that has shipped never changes, and this is what says so."""

from __future__ import annotations

from pathlib import Path

import pytest

from culmbin.store.migrations import MIGRATIONS
from culmbin.tools import check_migrations


def test_the_lock_on_disk_is_current() -> None:
    assert check_migrations.problems() == []
    assert check_migrations.unlocked() == []
    assert check_migrations.lock_path().name == "migrations.lock"


def test_every_migration_is_in_the_lock() -> None:
    locked = check_migrations.recorded()
    assert set(locked) == {migration.version for migration in MIGRATIONS}


def test_a_fingerprint_is_short_and_stable() -> None:
    digest = check_migrations.fingerprint("CREATE TABLE a (x TEXT);")
    assert len(digest) == 16
    assert digest == check_migrations.fingerprint("CREATE TABLE a (x TEXT);")


def test_a_reformatted_script_is_a_changed_script() -> None:
    """The only way to be sure a reformat changed nothing is to have not done it."""
    one = check_migrations.fingerprint("CREATE TABLE a (x TEXT);")
    other = check_migrations.fingerprint("CREATE TABLE a (x TEXT);\n")
    assert one != other


def test_a_changed_migration_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = tmp_path / "migrations.lock"
    lock.write_text("  1  0000000000000000  the version table itself\n", encoding="utf-8")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: lock)
    found = check_migrations.problems()
    assert any("has changed" in item for item in found)


def test_a_renamed_migration_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    digest = check_migrations.fingerprint(MIGRATIONS[0].script)
    lock = tmp_path / "migrations.lock"
    lock.write_text(f"  1  {digest}  something else entirely\n", encoding="utf-8")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: lock)
    found = check_migrations.problems()
    assert any("is now" in item for item in found)


def test_a_migration_that_has_gone_is_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Version ninety nine has been applied to books that exist."""
    lock = tmp_path / "migrations.lock"
    lock.write_text(check_migrations.render() + " 99  aaaaaaaaaaaaaaaa  a lost one\n", "utf-8")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: lock)
    found = check_migrations.problems()
    assert any("has gone" in item for item in found)


def test_a_missing_lock_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_migrations, "lock_path", lambda: tmp_path / "nothing.lock")
    assert check_migrations.problems() == [
        "migrations.lock: there is no lock. Write one with --write."
    ]


def test_a_new_migration_has_to_be_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "migrations.lock"
    digest = check_migrations.fingerprint(MIGRATIONS[0].script)
    lock.write_text(f"  1  {digest}  {MIGRATIONS[0].name}\n", encoding="utf-8")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: lock)
    assert check_migrations.problems() == []
    assert check_migrations.unlocked() == [item.version for item in MIGRATIONS[1:]]
    assert check_migrations.main([]) == 1


def test_writing_the_lock_records_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "migrations.lock"
    monkeypatch.setattr(check_migrations, "lock_path", lambda: lock)
    assert check_migrations.main(["--write"]) == 0
    assert lock.read_text(encoding="utf-8") == check_migrations.render()
    assert check_migrations.main([]) == 0
