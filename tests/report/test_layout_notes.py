"""The one line of prose a page adds when there is something to say.

Ten pages had written the condition out both ways round, which meant
reading one meant working out which way round it was.
"""

from __future__ import annotations

from culmbin.report.layout import note


def test_a_note_that_holds_is_its_lines() -> None:
    assert note("nothing went back.", when=True) == ["nothing went back."]


def test_a_note_that_does_not_hold_is_nothing() -> None:
    assert note("nothing went back.", when=False) == []


def test_a_note_of_several_lines_keeps_them_in_order() -> None:
    assert note("one", "two", when=True) == ["one", "two"]


def test_a_note_holds_by_default() -> None:
    assert note("always said") == ["always said"]


def test_a_note_of_nothing_is_nothing() -> None:
    assert note(when=True) == []
