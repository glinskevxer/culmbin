"""The intake pages."""

from __future__ import annotations

import datetime as dt

from culmbin.intake.desk import weigh_in
from culmbin.model.intake import Delivery
from culmbin.report.intake import day_sheet, grower_page, rejection_page
from culmbin.store.analyses import save_analysis
from culmbin.store.book import Book
from culmbin.store.deliveries import attach_sample
from tests.report.conftest import ARRIVED, HARVESTED, WEEK, lorry, sample

TODAY = dt.date(2025, 9, 22)


def test_the_day_sheet_counts_what_was_graded(week: Book) -> None:
    lorry(week, "W-1")
    lorry(week, "W-2", germ_capacity=90.0)
    text = day_sheet(week, WEEK, TODAY)
    assert "loads graded    2" in text
    assert "rejected        1 (50%)" in text


def test_a_load_waiting_for_a_sample_is_at_the_top(week: Book) -> None:
    weigh_in(
        week,
        Delivery(
            ticket="W-9",
            purchase="P-HOLB",
            party="HOLB",
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
            harvested=HARVESTED,
        ),
    )
    text = day_sheet(week, WEEK, TODAY)
    assert "waiting" in text
    assert "W-9" in text
    assert "sample" in text


def test_a_load_waiting_for_a_grading_says_so(week: Book) -> None:
    weigh_in(
        week,
        Delivery(
            ticket="W-9",
            purchase="P-HOLB",
            party="HOLB",
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
            harvested=HARVESTED,
        ),
    )
    save_analysis(week, sample("B-W-9"))
    attach_sample(week, "W-9", "B-W-9")
    assert "grading" in day_sheet(week, WEEK, TODAY)


def test_a_load_waiting_for_a_harvest_date_says_so(week: Book) -> None:
    weigh_in(
        week,
        Delivery(
            ticket="W-9",
            purchase="P-HOLB",
            party="HOLB",
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
        ),
    )
    assert "harvest date" in day_sheet(week, WEEK, TODAY)


def test_a_day_with_nothing_waiting_has_no_waiting_block(week: Book) -> None:
    """A page with six empty headings is a page nobody reads to the bottom of."""
    lorry(week, "W-1")
    assert "waiting" not in day_sheet(week, WEEK, TODAY)


def test_the_graded_block_carries_both_weights(week: Book) -> None:
    lorry(week, "W-1", moisture=15.0)
    text = day_sheet(week, WEEK, TODAY)
    assert "net" in text
    assert "settled" in text
    assert "accepted_on_deduction" in text


def test_the_rejection_page_names_the_reason(week: Book) -> None:
    lorry(week, "W-2", germ_capacity=90.0)
    text = rejection_page(week, WEEK)
    assert "W-2" in text
    assert "germination" in text


def test_a_week_with_no_rejections_says_so(week: Book) -> None:
    lorry(week, "W-1")
    assert "nothing went back." in rejection_page(week, WEEK)


def test_the_grower_page_carries_what_arrived_and_what_settled(week: Book) -> None:
    lorry(week, "W-1", moisture=15.0)
    text = grower_page(week, "HOLB", WEEK)
    assert "HOLB intake" in text
    assert "weighed" in text
    assert "settled" in text


def test_the_grower_page_leaves_other_growers_out(week: Book) -> None:
    lorry(week, "W-1", party="HOLB")
    lorry(week, "W-2", party="WYKE")
    text = grower_page(week, "HOLB", WEEK)
    assert "W-1" in text
    assert "W-2" not in text


def test_a_grower_with_nothing_delivered_says_so(week: Book) -> None:
    assert "nothing was delivered." in grower_page(week, "WYKE", WEEK)


def test_an_ungraded_load_is_marked_on_the_grower_page(week: Book) -> None:
    weigh_in(
        week,
        Delivery(
            ticket="W-9",
            purchase="P-HOLB",
            party="HOLB",
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
            harvested=HARVESTED,
        ),
    )
    assert "not graded" in grower_page(week, "HOLB", WEEK)


def test_every_page_ends_in_a_newline_and_has_no_trailing_space(week: Book) -> None:
    lorry(week, "W-1")
    for text in (
        day_sheet(week, WEEK, TODAY),
        rejection_page(week, WEEK),
        grower_page(week, "HOLB", WEEK),
    ):
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())
