"""Fixed width layout.

There is no malt in this module and there is none in these tests, which is
the point: the pages above it are then a function from records to rows.
"""

from __future__ import annotations

import pytest

from culmbin.report.layout import (
    GAP,
    PAGE_WIDTH,
    Align,
    Column,
    block,
    fit,
    heading,
    money,
    number,
    page,
    pairs,
    rule,
    table,
    table_block,
    wrap,
)


def test_a_cell_pads_to_the_width() -> None:
    assert fit("malt", 8) == "malt    "
    assert fit("malt", 8, Align.RIGHT) == "    malt"


def test_a_cell_that_fits_exactly_is_left_alone() -> None:
    assert fit("malt", 4) == "malt"


def test_a_cell_too_long_is_cut_and_marked() -> None:
    """A truncated name has to be obvious rather than merely wrong."""
    assert fit("Holbeach Grange", 8) == "Holbeac."


def test_a_cell_cut_to_one_character_has_no_room_to_mark() -> None:
    assert fit("Holbeach", 1) == "H"


def test_a_cell_of_no_width_is_nothing() -> None:
    assert fit("Holbeach", 0) == ""


def test_a_rule_is_the_width_asked_for() -> None:
    assert rule(10) == "-" * 10
    assert rule(10, "=") == "=" * 10
    assert len(rule()) == PAGE_WIDTH


def test_a_rule_needs_something_to_draw_with() -> None:
    with pytest.raises(ValueError, match="something to draw with"):
        rule(10, "")


def test_wrapping_breaks_on_spaces() -> None:
    assert wrap("the quick brown fox", 10) == ["the quick", "brown fox"]


def test_wrapping_something_short_is_one_line() -> None:
    assert wrap("malt", 10) == ["malt"]


def test_wrapping_nothing_is_one_empty_line() -> None:
    assert wrap("   ", 10) == [""]


def test_a_long_word_overhangs_rather_than_breaking() -> None:
    """Breaking a lot code in half is worse than a ragged margin."""
    assert wrap("L-2025-0412-A", 6) == ["L-2025-0412-A"]


def test_wrapping_to_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot wrap"):
        wrap("malt", 0)


def test_a_table_has_a_heading_and_a_rule() -> None:
    lines = table([Column("code"), Column("tonnes", Align.RIGHT)], [["L-1", "28.0"]])
    assert lines[0] == f"code{GAP}tonnes"
    assert set(lines[1]) == {"-"}
    assert lines[2] == f"L-1 {GAP}  28.0"


def test_a_column_is_as_wide_as_its_widest_cell() -> None:
    lines = table([Column("code"), Column("t")], [["L-2025-0412", "28"]])
    assert lines[0] == f"code       {GAP}t"


def test_a_column_with_a_width_keeps_it() -> None:
    lines = table([Column("code", width=4)], [["L-2025-0412"]])
    assert lines[2] == "L-2."


def test_a_table_with_no_rows_still_has_its_heading() -> None:
    lines = table([Column("code"), Column("tonnes")], [])
    assert len(lines) == 2
    assert lines[0] == f"code{GAP}tonnes"


def test_a_table_needs_columns() -> None:
    with pytest.raises(ValueError, match="needs columns"):
        table([], [["L-1"]])


def test_a_short_row_is_refused() -> None:
    """Filling it in quietly is how a column ends up one to the left."""
    with pytest.raises(ValueError, match="row 0 has 1 cells"):
        table([Column("code"), Column("tonnes")], [["L-1"]])


def test_trailing_space_is_stripped_from_every_line() -> None:
    lines = table([Column("code"), Column("note")], [["L-1", ""]])
    assert all(line == line.rstrip() for line in lines)


def test_pairs_line_the_labels_up() -> None:
    assert pairs([("lot", "L-1"), ("variety", "LAUR")]) == [
        "lot      L-1",
        "variety  LAUR",
    ]


def test_pairs_of_nothing_is_nothing() -> None:
    assert pairs([]) == []


def test_a_heading_has_a_rule_under_it() -> None:
    assert heading("intake") == ["intake", "======"]


def test_a_heading_rule_stops_at_the_page_width() -> None:
    lines = heading("x" * 200)
    assert len(lines[1]) == PAGE_WIDTH


def test_a_block_with_nothing_in_it_is_nothing() -> None:
    """A page with six empty headings is a page nobody reads to the bottom of."""
    assert block("rejections", []) == []


def test_a_block_with_something_keeps_its_title() -> None:
    assert block("rejections", ["W-1 germination"]) == ["rejections", "W-1 germination"]


def test_a_table_block_with_no_rows_is_nothing() -> None:
    """A table with no rows still has a heading, so `block` cannot tell."""
    assert table_block("waiting", [Column("ticket")], []) == []


def test_a_table_block_with_rows_has_its_title_and_table() -> None:
    lines = table_block("waiting", [Column("ticket")], [["W-1"]])
    assert lines[0] == "waiting"
    assert lines[-1] == "W-1"


def test_a_page_puts_a_blank_line_between_sections() -> None:
    assert page([["one"], ["two"]]) == "one\n\ntwo\n"


def test_a_page_leaves_out_empty_sections() -> None:
    assert page([["one"], [], ["two"]]) == "one\n\ntwo\n"


def test_a_page_of_nothing_is_nothing() -> None:
    assert page([]) == ""
    assert page([[], []]) == ""


def test_money_is_right_aligned() -> None:
    assert money("232.50", 10) == "    232.50"


def test_a_number_takes_the_places_it_is_given() -> None:
    assert number(28.1837, 2, 8) == "   28.18"
    assert number(28.1837, 0, 8) == "      28"
