"""Analyses in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Basis, Material
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.store.analyses import (
    add_result,
    analysis_note,
    count_analyses,
    find_analysis,
    get_analysis,
    list_analyses,
    save_analysis,
)
from culmbin.store.book import Book

TAKEN = dt.date(2025, 11, 4)


def malt(reference: str = "M-2025-0412", *results: Result, taken: dt.date = TAKEN) -> Analysis:
    return analysis_of(reference, Material.MALT, taken, [Result("malt_moisture", 4.2), *results])


def barley(reference: str = "B-2025-0918-03", taken: dt.date = TAKEN) -> Analysis:
    return analysis_of(reference, Material.BARLEY, taken, [Result("moisture", 12.4)])


def test_an_analysis_reads_back_the_way_it_went_in(book: Book) -> None:
    save_analysis(book, malt("M-1", Result("colour", 5.5)))
    read = get_analysis(book, "M-1")
    assert read.reference == "M-1"
    assert read.material is Material.MALT
    assert read.taken == TAKEN
    assert read.as_mapping() == {"malt_moisture": 4.2, "colour": 5.5}


def test_a_basis_survives_the_round_trip(book: Book) -> None:
    save_analysis(book, malt("M-1", Result("extract_fine", 81.4, Basis.DRY)))
    assert get_analysis(book, "M-1")["extract_fine"].basis is Basis.DRY


def test_the_results_come_back_in_the_order_they_went_in(book: Book) -> None:
    save_analysis(book, malt("M-1", Result("colour", 5.5), Result("friability", 84.0)))
    codes = [result.code for result in get_analysis(book, "M-1")]
    assert codes == ["malt_moisture", "colour", "friability"]


def test_an_analysis_that_is_not_there_says_which_one(book: Book) -> None:
    with pytest.raises(NotFoundError, match="M-9"):
        get_analysis(book, "M-9")


def test_finding_treats_absence_as_an_answer(book: Book) -> None:
    assert find_analysis(book, "M-9") is None


def test_saving_the_same_reference_twice_is_refused(book: Book) -> None:
    save_analysis(book, malt("M-1"))
    with pytest.raises(ConflictError):
        save_analysis(book, malt("M-1"))


def test_a_result_can_be_added_to_one_that_is_there(book: Book) -> None:
    """The lab reports in batches and the moisture comes back first."""
    save_analysis(book, malt("M-1"))
    updated = add_result(book, "M-1", Result("colour", 5.5))
    assert "colour" in updated
    assert get_analysis(book, "M-1")["colour"].value == pytest.approx(5.5)


def test_a_result_that_is_there_cannot_be_written_over(book: Book) -> None:
    """An analysis is corrected by issuing another one, not by editing this one."""
    save_analysis(book, malt("M-1", Result("colour", 5.5)))
    with pytest.raises(ConflictError, match="its own analysis"):
        add_result(book, "M-1", Result("colour", 5.9))


def test_the_first_number_survives_a_refused_correction(book: Book) -> None:
    save_analysis(book, malt("M-1", Result("colour", 5.5)))
    with pytest.raises(ConflictError):
        add_result(book, "M-1", Result("colour", 5.9))
    assert get_analysis(book, "M-1")["colour"].value == pytest.approx(5.5)


def test_adding_to_an_analysis_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError):
        add_result(book, "M-9", Result("colour", 5.5))


def test_a_whole_analysis_lands_together_or_not_at_all(book: Book) -> None:
    """The results go in the same transaction as the analysis they belong to."""
    save_analysis(book, malt("M-1", Result("colour", 5.5)))
    with pytest.raises(ConflictError):
        save_analysis(book, malt("M-1", Result("friability", 84.0)))
    assert count_analyses(book) == 1
    assert "friability" not in get_analysis(book, "M-1")


def test_a_note_is_kept_alongside_the_numbers(book: Book) -> None:
    save_analysis(book, malt("M-1"), note="sample re-milled, first grind lost")
    assert analysis_note(book, "M-1") == "sample re-milled, first grind lost"


def test_a_note_defaults_to_nothing(book: Book) -> None:
    save_analysis(book, malt("M-1"))
    assert analysis_note(book, "M-1") == ""


def test_a_note_on_something_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError):
        analysis_note(book, "M-9")


def test_the_listing_is_oldest_first(book: Book) -> None:
    save_analysis(book, malt("M-2", taken=dt.date(2025, 11, 6)))
    save_analysis(book, malt("M-1", taken=dt.date(2025, 11, 4)))
    assert [item.reference for item in list_analyses(book)] == ["M-1", "M-2"]


def test_the_listing_filters_by_material(book: Book) -> None:
    save_analysis(book, malt("M-1"))
    save_analysis(book, barley("B-1"))
    assert [item.reference for item in list_analyses(book, Material.BARLEY)] == ["B-1"]


def test_the_listing_filters_by_day_at_both_ends(book: Book) -> None:
    save_analysis(book, malt("M-1", taken=dt.date(2025, 11, 1)))
    save_analysis(book, malt("M-2", taken=dt.date(2025, 11, 5)))
    save_analysis(book, malt("M-3", taken=dt.date(2025, 11, 9)))
    references = [
        item.reference
        for item in list_analyses(book, since=dt.date(2025, 11, 3), until=dt.date(2025, 11, 7))
    ]
    assert references == ["M-2"]


def test_a_day_filter_includes_both_ends(book: Book) -> None:
    save_analysis(book, malt("M-1", taken=dt.date(2025, 11, 5)))
    listed = list_analyses(book, since=dt.date(2025, 11, 5), until=dt.date(2025, 11, 5))
    assert len(listed) == 1


def test_counting_narrows_by_material(book: Book) -> None:
    save_analysis(book, malt("M-1"))
    save_analysis(book, barley("B-1"))
    assert count_analyses(book) == 2
    assert count_analyses(book, Material.MALT) == 1


def test_an_empty_book_counts_nothing(book: Book) -> None:
    assert count_analyses(book) == 0
    assert list_analyses(book) == ()
