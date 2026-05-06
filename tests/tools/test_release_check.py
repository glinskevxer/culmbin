"""Everything that makes a bad release day, asked before anybody ships."""

from __future__ import annotations

import pytest

from culmbin import __version__
from culmbin.store.migrations import latest_version
from culmbin.tools import release_check


def test_the_check_passes_on_this_tree() -> None:
    assert release_check.problems() == []


def test_the_package_and_pyproject_agree() -> None:
    assert release_check.declared_version() == __version__


def test_the_changelog_has_an_entry_for_this_version() -> None:
    assert __version__ in release_check.changelog_versions()


def test_the_newest_changelog_entry_is_this_version() -> None:
    assert release_check.changelog_versions()[0] == __version__


def test_the_version_is_three_numbers() -> None:
    assert len(__version__.split(".")) == 3


def test_the_changelog_entry_says_which_schema_it_ships() -> None:
    """A version that changes the schema and does not say so is one nobody backs up for."""
    assert release_check.schema_named() == latest_version()


def test_the_newest_entry_is_the_one_read() -> None:
    entry = release_check.newest_entry()
    assert entry.startswith(__version__)


def test_an_entry_with_no_schema_line_says_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release_check, "newest_entry", lambda: "0.9.0\n\nSome changes.\n")
    assert release_check.schema_named() is None


def test_an_entry_naming_the_wrong_schema_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release_check, "newest_entry", lambda: "0.9.0\n\nSchema version 2.\n")
    found = release_check.problems()
    assert any("and the migrations are at" in item for item in found)


def test_a_missing_changelog_entry_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release_check, "changelog_versions", list)
    found = release_check.problems()
    assert any("no version entries" in item for item in found)
