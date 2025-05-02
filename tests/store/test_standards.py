"""Quality standards in the book."""

from __future__ import annotations

from decimal import Decimal

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.intake.standard import Standard
from culmbin.store.book import Book
from culmbin.store.standards import (
    add_standard,
    copy_standard,
    find_standard,
    get_standard,
    list_standards,
)


def standard(name: str = "malting 2025", **kwargs: object) -> Standard:
    fields: dict[str, object] = {"name": name}
    fields.update(kwargs)
    return Standard(**fields)  # type: ignore[arg-type]


def test_a_standard_reads_back_the_way_it_went_in(book: Book) -> None:
    add_standard(book, standard())
    assert get_standard(book, "malting 2025") == standard()


def test_the_prices_come_back_as_decimals(book: Book) -> None:
    """Money is text in the book, because 232.50 is not a float."""
    add_standard(book, standard(drying_per_point=Decimal("2.40")))
    read = get_standard(book, "malting 2025")
    assert read.drying_per_point == Decimal("2.40")
    assert isinstance(read.drying_per_point, Decimal)


def test_a_standard_that_is_not_there_says_which_one(book: Book) -> None:
    with pytest.raises(NotFoundError, match="malting 2024"):
        get_standard(book, "malting 2024")


def test_finding_treats_absence_as_an_answer(book: Book) -> None:
    assert find_standard(book, "malting 2025") is None


def test_writing_over_a_standard_is_refused(book: Book) -> None:
    """A used standard cannot change, because settlements quote it."""
    add_standard(book, standard())
    with pytest.raises(ConflictError):
        add_standard(book, standard(moisture_base=13.0))


def test_the_thresholds_survive_the_round_trip(book: Book) -> None:
    add_standard(
        book,
        standard(
            moisture_base=13.0,
            nitrogen_max=1.75,
            screenings_free=1.5,
            germination_floor=97.0,
        ),
    )
    read = get_standard(book, "malting 2025")
    assert read.moisture_base == pytest.approx(13.0)
    assert read.nitrogen_max == pytest.approx(1.75)
    assert read.screenings_free == pytest.approx(1.5)
    assert read.germination_floor == pytest.approx(97.0)


def test_the_listing_is_in_name_order(book: Book) -> None:
    add_standard(book, standard("malting 2025"))
    add_standard(book, standard("distilling 2025"))
    assert [item.name for item in list_standards(book)] == ["distilling 2025", "malting 2025"]


def test_an_empty_book_lists_nothing(book: Book) -> None:
    assert list_standards(book) == ()


def test_copying_carries_every_threshold_over(book: Book) -> None:
    add_standard(book, standard(nitrogen_max=1.75, drying_per_point=Decimal("2.65")))
    copy_standard(book, "malting 2025", "malting 2026")
    copy = get_standard(book, "malting 2026")
    assert copy.nitrogen_max == pytest.approx(1.75)
    assert copy.drying_per_point == Decimal("2.65")
    assert copy.name == "malting 2026"


def test_copying_leaves_the_original_alone(book: Book) -> None:
    add_standard(book, standard())
    copy_standard(book, "malting 2025", "malting 2026")
    assert get_standard(book, "malting 2025") == standard()


def test_copying_onto_a_name_that_is_taken_is_refused(book: Book) -> None:
    add_standard(book, standard("malting 2025"))
    add_standard(book, standard("malting 2026"))
    with pytest.raises(ConflictError, match="already a standard"):
        copy_standard(book, "malting 2025", "malting 2026")


def test_copying_something_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError):
        copy_standard(book, "malting 2024", "malting 2026")


def test_the_book_refuses_a_band_the_wrong_way_round(book: Book) -> None:
    """The record checks it and so does the book, because both get written to."""
    with pytest.raises(ConflictError):
        book.execute(
            "INSERT INTO standard (name, moisture_base, moisture_reject, nitrogen_min, "
            "nitrogen_max, nitrogen_reject, screenings_free, screenings_reject, "
            "germination_floor, energy_floor, admixture_reject, drying_per_point, "
            "nitrogen_step, nitrogen_per_step) VALUES "
            "('bad', 12.5, 20.0, 1.9, 1.4, 2.05, 2.0, 5.0, 98.0, 95.0, 2.0, '2.40', 0.05, '1.50')"
        )
