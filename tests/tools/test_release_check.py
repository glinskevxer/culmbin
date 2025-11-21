"""Everything that makes a bad release day, asked before anybody ships."""

from __future__ import annotations

from culmbin import __version__
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
