"""A walk for a machine that has just installed the wheel."""

from __future__ import annotations

import pytest

from culmbin.store.book import Book
from culmbin.tools import smoke


def test_the_walk_gets_a_lorry_to_a_settlement(book: Book) -> None:
    said = smoke.walk(book)
    assert "registers written" in said
    assert any("settled at 6551.85" in line for line in said)


def test_the_walk_says_what_is_left_on_the_purchase(book: Book) -> None:
    said = smoke.walk(book)
    assert any("still to come on P-1" in line for line in said)


def test_the_smoke_test_runs_in_a_book_of_its_own(capsys: pytest.CaptureFixture[str]) -> None:
    """It writes into a temporary directory, so it runs anywhere."""
    assert smoke.main([]) == 0
    assert "the wheel works." in capsys.readouterr().out


def test_the_quiet_form_says_only_whether_it_worked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert smoke.main(["--quiet"]) == 0
    output = capsys.readouterr().out
    assert output.strip() == "smoke: the wheel works."
