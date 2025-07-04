"""Specifications in the book."""

from __future__ import annotations

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Basis, Material
from culmbin.model.spec import Clause, Specification, specification
from culmbin.store.book import Book
from culmbin.store.specs import (
    copy_specification,
    find_specification,
    get_specification,
    list_specifications,
    save_specification,
    specifications_using,
)


def lager(name: str = "pale ale 2025") -> Specification:
    return specification(
        name,
        Material.MALT,
        [
            Clause("extract_fine", basis=Basis.DRY, minimum=80.5),
            Clause("colour", minimum=2.5, maximum=4.5),
            Clause("total_protein", basis=Basis.DRY, maximum=10.5),
        ],
        ["LAUR"],
    )


def test_a_specification_reads_back_the_way_it_went_in(stocked: Book) -> None:
    save_specification(stocked, lager())
    assert get_specification(stocked, "pale ale 2025") == lager()


def test_the_clauses_keep_the_order_they_were_written_in(stocked: Book) -> None:
    save_specification(stocked, lager())
    read = get_specification(stocked, "pale ale 2025")
    assert [clause.code for clause in read] == ["extract_fine", "colour", "total_protein"]


def test_a_clause_basis_survives_the_round_trip(stocked: Book) -> None:
    save_specification(stocked, lager())
    read = get_specification(stocked, "pale ale 2025")
    assert read.clauses[0].basis is Basis.DRY
    assert read.clauses[1].basis is None


def test_both_bounds_survive_the_round_trip(stocked: Book) -> None:
    save_specification(stocked, lager())
    read = get_specification(stocked, "pale ale 2025")
    assert read.clauses[1].minimum == pytest.approx(2.5)
    assert read.clauses[1].maximum == pytest.approx(4.5)
    assert read.clauses[0].maximum is None


def test_the_varieties_survive_the_round_trip(stocked: Book) -> None:
    save_specification(stocked, lager())
    assert get_specification(stocked, "pale ale 2025").varieties == frozenset({"LAUR"})


def test_a_specification_that_is_not_there_says_which_one(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="pale ale 2024"):
        get_specification(stocked, "pale ale 2024")
    assert find_specification(stocked, "pale ale 2024") is None


def test_writing_over_a_specification_is_refused(stocked: Book) -> None:
    save_specification(stocked, lager())
    with pytest.raises(ConflictError):
        save_specification(stocked, lager())


def test_the_book_refuses_the_same_analyte_twice(stocked: Book) -> None:
    save_specification(stocked, lager())
    with pytest.raises(ConflictError):
        stocked.execute(
            "INSERT INTO clause (specification, seq, code, minimum) "
            "VALUES ('lager 2025', 9, 'colour', 1.0)"
        )


def test_the_book_refuses_a_clause_with_no_bounds(stocked: Book) -> None:
    save_specification(stocked, lager())
    with pytest.raises(ConflictError):
        stocked.execute(
            "INSERT INTO clause (specification, seq, code) VALUES ('lager 2025', 9, 'friability')"
        )


def test_a_variety_that_is_not_listed_is_refused(stocked: Book) -> None:
    spec = specification(
        "distilling 2025", Material.MALT, [Clause("colour", maximum=4.0)], ["NOPE"]
    )
    with pytest.raises(ConflictError, match="does not hold"):
        save_specification(stocked, spec)


def test_the_listing_narrows_by_material(stocked: Book) -> None:
    save_specification(stocked, lager())
    barley = specification("intake 2025", Material.BARLEY, [Clause("screenings", maximum=2.0)])
    save_specification(stocked, barley)
    assert [item.name for item in list_specifications(stocked)] == [
        "intake 2025",
        "lager 2025",
        "pale ale 2025",
    ]
    only = list_specifications(stocked, Material.BARLEY)
    assert [item.name for item in only] == ["intake 2025"]


def test_copying_carries_every_clause_over(stocked: Book) -> None:
    save_specification(stocked, lager())
    copy_specification(stocked, "pale ale 2025", "pale ale 2026")
    copy = get_specification(stocked, "pale ale 2026")
    assert copy.clauses == get_specification(stocked, "pale ale 2025").clauses
    assert copy.varieties == frozenset({"LAUR"})


def test_copying_onto_a_name_that_is_taken_is_refused(stocked: Book) -> None:
    save_specification(stocked, lager())
    save_specification(stocked, lager("pale ale 2026"))
    with pytest.raises(ConflictError, match="already a specification"):
        copy_specification(stocked, "pale ale 2025", "pale ale 2026")


def test_copying_something_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        copy_specification(stocked, "pale ale 2024", "pale ale 2026")


def test_the_laboratory_can_ask_whose_specification_cares(stocked: Book) -> None:
    save_specification(stocked, lager())
    save_specification(stocked, lager("pale ale 2026"))
    assert specifications_using(stocked, "colour") == (
        "lager 2025",
        "pale ale 2025",
        "pale ale 2026",
    )
    assert specifications_using(stocked, "friability") == ()


def test_a_book_holds_only_what_was_written_into_it(stocked: Book) -> None:
    assert [item.name for item in list_specifications(stocked)] == ["lager 2025"]
