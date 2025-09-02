"""The pages about one piece."""

from __future__ import annotations

import datetime as dt

from culmbin.model.enums import PieceStage
from culmbin.process.floor import cast, charge, load_kiln, strip_kiln
from culmbin.report.process import balance_page, piece_page
from culmbin.store.book import Book
from culmbin.store.pieces import add_reading
from culmbin.units.clock import Leg
from tests.support.records import a_piece

CAST = dt.date(2025, 11, 5)
KILNED = dt.date(2025, 11, 9)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


def finished(plant: Book, code: str = "2025-118") -> None:
    charge(plant, a_piece(code), PROGRAMME, SCHEDULE, CURVE)
    add_reading(plant, code, PieceStage.STEEPING, Leg(hours=48.0, celsius=14.0))
    cast(plant, code, "G1", CAST, 71.8, 44.8, depth_cm=85.0)
    add_reading(plant, code, PieceStage.GERMINATING, Leg(hours=96.0, celsius=16.0))
    load_kiln(plant, code, "K1", dt.date(2025, 11, 8))
    strip_kiln(plant, code, KILNED, 37.9, 4.4, 1.9)


def test_a_piece_page_carries_the_charge_and_its_dry_matter(plant: Book) -> None:
    finished(plant)
    text = piece_page(plant, "2025-118")
    assert "piece 2025-118" in text
    assert "45.00t at 12.0%" in text
    assert "39.60t" in text


def test_a_piece_page_lists_the_movements_in_order(plant: Book) -> None:
    finished(plant)
    text = piece_page(plant, "2025-118")
    lines = text.splitlines()
    assert lines.index("movements") < lines.index("weights")
    assert "steeping" in text
    assert "kilned" in text


def test_a_piece_page_names_the_three_recipes(plant: Book) -> None:
    finished(plant)
    text = piece_page(plant, "2025-118")
    assert PROGRAMME in text
    assert SCHEDULE in text
    assert CURVE in text


def test_the_clock_block_keeps_the_stages_apart(plant: Book) -> None:
    """The steep hours are on the piece and are not on the box clock."""
    finished(plant)
    text = piece_page(plant, "2025-118")
    assert "clock" in text
    assert "1152" in text


def test_a_piece_with_no_weights_still_has_a_page(plant: Book) -> None:
    charge(plant, a_piece(), PROGRAMME, SCHEDULE, CURVE)
    text = piece_page(plant, "2025-118")
    assert "piece 2025-118" in text
    assert "weights" not in text


def test_the_balance_page_carries_loss_and_yield(plant: Book) -> None:
    finished(plant)
    text = balance_page(plant, ("2025-118",))
    assert "loss %" in text
    assert "yield %" in text
    assert "loss is dry matter and yield is not" in text


def test_a_piece_that_was_not_weighed_is_left_off(plant: Book) -> None:
    charge(plant, a_piece(), PROGRAMME, SCHEDULE, CURVE)
    assert "no piece has been weighed at every point." in balance_page(plant, ("2025-118",))


def test_the_balance_page_finds_finished_pieces_on_its_own(plant: Book) -> None:
    finished(plant)
    assert "2025-118" in balance_page(plant)


def test_both_pages_end_in_a_newline_and_have_no_trailing_space(plant: Book) -> None:
    finished(plant)
    for text in (piece_page(plant, "2025-118"), balance_page(plant)):
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())
