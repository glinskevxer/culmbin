"""What can be promised: contracts against malt, and malt against contracts."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import StateError
from culmbin.model.enums import ContractState
from culmbin.model.sales import Contract
from culmbin.sales.cover import (
    contracts_a_lot_could_serve,
    cover,
    lots_a_contract_could_take,
    orphan_lots,
)
from culmbin.sales.desk import allocate
from culmbin.store.book import Book
from culmbin.store.contracts import add_contract
from tests.support.books import CONTRACT_WINDOW, SIGNED, a_lot

ON = dt.date(2025, 11, 20)


def another_contract(
    desk: Book, code: str, variety: str | None = None, spec: str = "lager 2025"
) -> None:
    add_contract(
        desk,
        Contract(
            code=code,
            customer="BRWY",
            specification=spec,
            tonnes=500.0,
            moisture=4.5,
            price_per_tonne=Decimal("410.00"),
            window=CONTRACT_WINDOW,
            signed=SIGNED,
            state=ContractState.SIGNED,
            variety=variety,
        ),
    )


def test_a_desk_with_a_lot_and_a_contract_is_short(desk: Book) -> None:
    where = cover(desk)
    assert where.sealed_tonnes == pytest.approx(60.0)
    assert where.free_tonnes == pytest.approx(60.0)
    assert where.outstanding_tonnes == pytest.approx(2400.0)
    assert where.short_by == pytest.approx(2340.0)
    assert not where.covered


def test_allocating_takes_malt_out_of_the_free_figure(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 40.0, ON)
    assert cover(desk).free_tonnes == pytest.approx(20.0)


def test_a_desk_with_no_contracts_is_covered(desk: Book) -> None:
    desk.execute("UPDATE contract SET state = 'closed'")
    where = cover(desk)
    assert where.outstanding_tonnes == pytest.approx(0.0)
    assert where.covered
    assert where.short_by == pytest.approx(0.0)


def test_the_floor_is_counted_separately_and_never_added(desk: Book) -> None:
    """Malt on the floor is four days off and might come off out of specification."""
    before = cover(desk)
    desk.execute(
        "INSERT INTO vessel (code, name, kind, commissioned, charge_limit_t) "
        "VALUES ('S1', 'steep 1', 'steep', '1998-04-01', 45.0)"
    )
    desk.execute(
        "INSERT INTO piece (code, variety, crop_year, style, charge_tonnes, charge_moisture, "
        "started, stage, vessel) VALUES "
        "('2025-200', 'LAUR', 2025, 'lager', 45.0, 12.0, '2025-11-03', 'steeping', 'S1')"
    )
    after = cover(desk)
    assert after.free_tonnes == pytest.approx(before.free_tonnes)
    assert after.coming_tonnes > 0.0
    assert after.short_by_with_the_floor < after.short_by


def test_a_finished_piece_is_not_coming(desk: Book) -> None:
    desk.execute(
        "INSERT INTO piece (code, variety, crop_year, style, charge_tonnes, charge_moisture, "
        "started, stage, vessel) VALUES "
        "('2025-201', 'LAUR', 2025, 'lager', 45.0, 12.0, '2025-11-03', 'binned', NULL)"
    )
    assert cover(desk).coming_tonnes == pytest.approx(0.0)


def test_a_lot_that_meets_a_contract_could_serve_it(desk: Book) -> None:
    found = contracts_a_lot_could_serve(desk, "L-CLEAN")
    assert [contract.code for contract in found] == ["C-2025-031"]


def test_a_lot_outside_the_specification_could_serve_nothing(desk: Book) -> None:
    a_lot(desk, "L-DARK", "B05", ("LAUR",), "M-DARK", colour=6.2)
    assert contracts_a_lot_could_serve(desk, "L-DARK") == ()


def test_a_contract_naming_a_variety_is_left_out_for_a_mixed_lot(desk: Book) -> None:
    a_lot(desk, "L-MIXED", "B05", ("LAUR", "DIAB"), "M-MIXED")
    another_contract(desk, "C-VARIETY", variety="LAUR")
    found = contracts_a_lot_could_serve(desk, "L-MIXED")
    assert "C-VARIETY" not in [contract.code for contract in found]


def test_an_uncertified_lot_cannot_be_asked_about(desk: Book) -> None:
    desk.execute("UPDATE malt_lot SET analysis = NULL WHERE code = 'L-CLEAN'")
    with pytest.raises(StateError, match="nothing can be said"):
        contracts_a_lot_could_serve(desk, "L-CLEAN")


def test_a_contract_says_which_lots_it_could_take(desk: Book) -> None:
    assert lots_a_contract_could_take(desk, "C-2025-031") == ("L-CLEAN",)


def test_a_lot_with_nothing_left_is_not_offered(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 60.0, ON)
    assert lots_a_contract_could_take(desk, "C-2025-031") == ()


def test_a_lot_no_contract_can_take_is_an_orphan(desk: Book) -> None:
    """A lot that meets nothing is stock in name only."""
    a_lot(desk, "L-DARK", "B05", ("LAUR",), "M-DARK", colour=6.2)
    assert orphan_lots(desk) == ("L-DARK",)


def test_a_lot_something_can_take_is_not_an_orphan(desk: Book) -> None:
    assert "L-CLEAN" not in orphan_lots(desk)


def test_a_lot_that_is_empty_is_not_an_orphan_either(desk: Book) -> None:
    a_lot(desk, "L-DARK", "B05", ("LAUR",), "M-DARK", colour=6.2)
    desk.execute(
        "INSERT INTO shipment (code, contract, lot, tonnes, moisture, despatched, state) "
        "VALUES ('S-9', 'C-2025-031', 'L-DARK', 60.0, 4.2, '2025-11-20', 'planned')"
    )
    assert orphan_lots(desk) == ()


def test_both_varieties_are_on_the_list_for_these_tests(desk: Book) -> None:
    codes = [row["code"] for row in desk.query("SELECT code FROM variety ORDER BY code")]
    assert codes == ["DIAB", "LAUR"]
