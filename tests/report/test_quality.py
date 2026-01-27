"""The quality page."""

from __future__ import annotations

import datetime as dt

from culmbin.model.complaint import Complaint
from culmbin.model.enums import ComplaintKind, ComplaintState
from culmbin.report.quality import quality_page
from culmbin.store.book import Book
from culmbin.store.complaints import close, raise_complaint
from culmbin.units.season import Window

RAISED = dt.date(2026, 1, 14)
TODAY = dt.date(2026, 1, 31)
MONTH = Window(dt.date(2026, 1, 1), dt.date(2026, 1, 31))


def a_complaint(desk: Book, code: str = "Q-1", **kwargs: object) -> None:
    fields: dict[str, object] = {
        "customer": "BRWY",
        "kind": ComplaintKind.COLOUR,
        "raised": RAISED,
        "summary": "wort came out two EBC darker than the certificate",
    }
    fields.update(kwargs)
    raise_complaint(desk, Complaint(code=code, **fields))  # type: ignore[arg-type]


def test_a_month_with_nothing_says_so(desk: Book) -> None:
    assert "nobody has complained." in quality_page(desk, MONTH, TODAY)


def test_a_complaint_is_on_the_page(desk: Book) -> None:
    a_complaint(desk)
    text = quality_page(desk, MONTH, TODAY)
    assert "Q-1" in text
    assert "raised            1" in text


def test_the_untraceable_block_is_at_the_top(desk: Book) -> None:
    """They are the ones a quality meeting quietly leaves out."""
    a_complaint(desk)
    text = quality_page(desk, MONTH, TODAY)
    lines = text.splitlines()
    assert "no shipment to walk back to" in text
    assert lines.index("no shipment to walk back to") < lines.index("still open")


def test_a_complaint_about_paperwork_is_not_untraceable(desk: Book) -> None:
    a_complaint(desk, kind=ComplaintKind.PAPERWORK)
    text = quality_page(desk, MONTH, TODAY)
    assert "no shipment to walk back to" not in text
    assert "cannot be traced  0" in text


def test_a_closed_complaint_is_off_the_open_block(desk: Book) -> None:
    a_complaint(desk)
    close(desk, "Q-1", ComplaintState.UPHELD, dt.date(2026, 1, 20), "kiln ran hot")
    text = quality_page(desk, MONTH, TODAY)
    assert "still open" not in text
    assert "upheld            1" in text


def test_the_counts_carry_every_kind(desk: Book) -> None:
    a_complaint(desk)
    text = quality_page(desk, MONTH, TODAY)
    for kind in ComplaintKind:
        assert str(kind) in text


def test_the_days_column_counts_to_the_day_asked_for(desk: Book) -> None:
    a_complaint(desk)
    text = quality_page(desk, MONTH, dt.date(2026, 1, 20))
    assert " 6 " in text or " 6" in text


def test_the_page_ends_in_a_newline_and_has_no_trailing_space(desk: Book) -> None:
    a_complaint(desk)
    text = quality_page(desk, MONTH, TODAY)
    assert text.endswith("\n")
    assert all(line == line.rstrip() for line in text.splitlines())
