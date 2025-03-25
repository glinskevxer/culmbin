"""Growers, merchants, customers and hauliers."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import NotFoundError, ValidationError
from culmbin.model.enums import Role
from culmbin.model.party import Party, register_of

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


def test_a_party_prints_as_code_and_name() -> None:
    assert str(grower()) == "HOLB Holbeach Grange"


def test_a_party_needs_a_code_and_a_name() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        grower(" ")
    with pytest.raises(ValidationError, match="has no name"):
        grower(name="  ")


def test_only_a_grower_has_a_holding_number() -> None:
    with pytest.raises(ValidationError, match="no holding number"):
        grower(role=Role.CUSTOMER)


def test_a_customer_without_a_holding_is_fine() -> None:
    party = Party("BRWY", "Sheldrake Brewing", Role.CUSTOMER, OPENED)
    assert party.holding is None


def test_a_party_closed_before_it_opened_is_refused() -> None:
    with pytest.raises(ValidationError, match="closed before it opened"):
        grower(closed=dt.date(2010, 1, 1))


def test_trading_starts_on_the_day_they_opened() -> None:
    assert not grower().trading_on(dt.date(2011, 5, 31))
    assert grower().trading_on(OPENED)


def test_trading_stops_on_the_day_they_closed() -> None:
    gone = grower(closed=dt.date(2024, 9, 1))
    assert gone.trading_on(dt.date(2024, 8, 31))
    assert not gone.trading_on(dt.date(2024, 9, 1))


def test_a_register_looks_a_party_up() -> None:
    register = register_of([grower("HOLB"), grower("WYKE", name="Wykeham Farms")])
    assert register["WYKE"].name == "Wykeham Farms"
    assert len(register) == 2


def test_a_party_that_is_not_there_says_what_was_asked_for() -> None:
    with pytest.raises(NotFoundError, match="NOPE"):
        register_of([grower()])["NOPE"]


def test_two_parties_with_one_code_are_refused() -> None:
    with pytest.raises(ValidationError, match="share the code HOLB"):
        register_of([grower("HOLB"), grower("HOLB")])


def test_one_company_in_two_roles_is_two_rows() -> None:
    """The same name twice under two codes is the shape this is meant to have."""
    register = register_of(
        [
            grower("WYKE"),
            Party("WYKEM", "Wykeham Farms", Role.MERCHANT, OPENED),
        ]
    )
    assert len(register.of_role(Role.GROWER)) == 1
    assert len(register.of_role(Role.MERCHANT)) == 1


def test_a_register_lists_who_was_trading_on_a_day() -> None:
    register = register_of([grower("HOLB"), grower("OLD", closed=dt.date(2020, 1, 1))])
    codes = [party.code for party in register.trading_on(dt.date(2024, 1, 1))]
    assert codes == ["HOLB"]


def test_a_register_iterates_in_order() -> None:
    register = register_of([grower("HOLB"), grower("WYKE")])
    assert [party.code for party in register] == ["HOLB", "WYKE"]
