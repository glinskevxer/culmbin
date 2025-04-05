"""The party register in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, ValidationError
from culmbin.model.enums import Role
from culmbin.model.party import Party
from culmbin.store.book import Book
from culmbin.store.parties import (
    add_party,
    close_party,
    find_party,
    get_party,
    list_parties,
    update_party,
)

OPENED = dt.date(2011, 6, 1)


def grower(code: str = "HOLB", **kwargs: object) -> Party:
    fields: dict[str, object] = {
        "name": "Holbeach Grange",
        "role": Role.GROWER,
        "opened": OPENED,
        "holding": "12/345/6789",
    }
    fields.update(kwargs)
    return Party(code=code, **fields)  # type: ignore[arg-type]


def test_a_party_reads_back_the_way_it_went_in(book: Book) -> None:
    add_party(book, grower())
    assert get_party(book, "HOLB") == grower()


def test_a_party_survives_the_connection_that_wrote_it(book: Book) -> None:
    """The write is committed, not left in an open transaction."""
    add_party(book, grower())
    assert book.scalar("SELECT count(*) FROM party") == 1


def test_a_party_that_is_not_there_says_which_one(book: Book) -> None:
    with pytest.raises(NotFoundError, match="HOLB"):
        get_party(book, "HOLB")


def test_finding_treats_absence_as_an_answer(book: Book) -> None:
    assert find_party(book, "HOLB") is None
    add_party(book, grower())
    assert find_party(book, "HOLB") == grower()


def test_adding_the_same_code_twice_is_refused(book: Book) -> None:
    add_party(book, grower())
    with pytest.raises(ConflictError, match="already holds"):
        add_party(book, grower(name="Somebody Else"))


def test_a_closed_date_and_a_holding_survive_the_round_trip(book: Book) -> None:
    party = grower(closed=dt.date(2024, 9, 1))
    add_party(book, party)
    read = get_party(book, "HOLB")
    assert read.closed == dt.date(2024, 9, 1)
    assert read.holding == "12/345/6789"


def test_a_customer_reads_back_with_no_holding(book: Book) -> None:
    add_party(book, Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, OPENED))
    assert get_party(book, "BRWY").holding is None


def test_updating_changes_what_was_given(book: Book) -> None:
    add_party(book, grower())
    update_party(book, grower(name="Holbeach Grange Farms"))
    assert get_party(book, "HOLB").name == "Holbeach Grange Farms"


def test_updating_something_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError, match="HOLB"):
        update_party(book, grower())


def test_the_register_comes_back_in_code_order(book: Book) -> None:
    add_party(book, grower("WYKE", name="Wykeham Farms"))
    add_party(book, grower("HOLB"))
    assert [party.code for party in list_parties(book)] == ["HOLB", "WYKE"]


def test_the_register_filters_by_role(book: Book) -> None:
    add_party(book, grower("HOLB"))
    add_party(book, Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, OPENED))
    assert [party.code for party in list_parties(book, Role.CUSTOMER)] == ["BRWY"]
    assert len(list_parties(book)) == 2


def test_an_empty_register_is_empty(book: Book) -> None:
    assert len(list_parties(book)) == 0


def test_closing_stops_them_trading_from_that_day(book: Book) -> None:
    add_party(book, grower())
    close_party(book, "HOLB", dt.date(2024, 9, 1))
    party = get_party(book, "HOLB")
    assert not party.trading_on(dt.date(2024, 9, 1))
    assert party.trading_on(dt.date(2024, 8, 31))


def test_closing_somebody_twice_is_refused(book: Book) -> None:
    """The second date is nearly always a typing mistake."""
    add_party(book, grower())
    close_party(book, "HOLB", dt.date(2024, 9, 1))
    with pytest.raises(ConflictError, match="already closed"):
        close_party(book, "HOLB", dt.date(2024, 10, 1))


def test_closing_somebody_who_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError):
        close_party(book, "HOLB", dt.date(2024, 9, 1))


def test_the_book_refuses_what_the_record_refuses(book: Book) -> None:
    """Both ends check the holding rule, because both ends get written to."""
    with pytest.raises(ValidationError):
        grower(role=Role.CUSTOMER)
    with pytest.raises(ConflictError):
        book.execute(
            "INSERT INTO party (code, name, role, opened, holding) "
            "VALUES ('X', 'X', 'customer', '2025-01-01', '12/345')"
        )
