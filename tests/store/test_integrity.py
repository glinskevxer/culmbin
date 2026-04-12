"""Asking a book whether it still makes sense."""

from __future__ import annotations

import datetime as dt

from culmbin.store.book import Book
from culmbin.store.integrity import (
    Finding,
    crossing_rules,
    faults,
    sound,
    sqlite_says,
    summary,
    tables_holding_nothing,
    worth_a_look,
)
from tests.support.books import a_lot

ON = dt.date(2025, 11, 20)


def test_a_fresh_book_is_sound(book: Book) -> None:
    assert sqlite_says(book) == []
    assert faults(book) == []
    assert sound(book)


def test_a_stocked_book_is_sound(desk: Book) -> None:
    assert sound(desk)


def test_a_finding_prints_as_a_line() -> None:
    assert str(Finding("lot", "L-1 has no analysis")) == "lot: L-1 has no analysis"


def test_a_shipment_against_an_unsigned_contract_is_a_fault(desk: Book) -> None:
    desk.execute(
        "INSERT INTO shipment (code, contract, lot, tonnes, moisture, despatched, state) "
        "VALUES ('S-1', 'C-2025-031', 'L-CLEAN', 28.0, 4.2, '2025-11-20', 'planned')"
    )
    desk.execute("UPDATE contract SET state = 'closed' WHERE code = 'C-2025-031'")
    found = crossing_rules(desk)
    assert any("which is not signed" in item.detail for item in found)
    assert not sound(desk)


def test_a_cancelled_shipment_against_a_closed_contract_is_not_a_fault(desk: Book) -> None:
    desk.execute(
        "INSERT INTO shipment (code, contract, lot, tonnes, moisture, despatched, state) "
        "VALUES ('S-1', 'C-2025-031', 'L-CLEAN', 28.0, 4.2, '2025-11-20', 'cancelled')"
    )
    desk.execute("UPDATE contract SET state = 'closed' WHERE code = 'C-2025-031'")
    assert sound(desk)


def test_an_uncertified_lot_that_has_shipped_is_a_fault(desk: Book) -> None:
    desk.execute(
        "INSERT INTO shipment (code, contract, lot, tonnes, moisture, despatched, state) "
        "VALUES ('S-1', 'C-2025-031', 'L-CLEAN', 28.0, 4.2, '2025-11-20', 'despatched')"
    )
    desk.execute("UPDATE malt_lot SET analysis = NULL WHERE code = 'L-CLEAN'")
    found = crossing_rules(desk)
    assert any("has no analysis and has been shipped" in item.detail for item in found)


def test_two_pieces_in_one_vessel_is_a_fault(desk: Book) -> None:
    desk.execute(
        "INSERT INTO vessel (code, name, kind, commissioned, charge_limit_t) "
        "VALUES ('S1', 'steep 1', 'steep', '1998-04-01', 45.0)"
    )
    for code in ("2025-300", "2025-301"):
        desk.execute(
            "INSERT INTO piece (code, variety, crop_year, style, charge_tonnes, "
            "charge_moisture, started, stage, vessel) VALUES "
            f"('{code}', 'LAUR', 2025, 'lager', 45.0, 12.0, '2025-11-03', 'steeping', 'S1')"
        )
    found = crossing_rules(desk)
    assert any("so is something else" in item.detail for item in found)


def test_a_piece_with_no_lorry_loads_is_odd_and_not_wrong(desk: Book) -> None:
    """The walk stops at the steep, which is worth a look and is not a fault."""
    found = worth_a_look(desk)
    assert any("no lorry loads recorded" in item.detail for item in found)
    assert sound(desk)


def test_a_lot_bigger_than_its_bin_is_odd(desk: Book) -> None:
    desk.execute("UPDATE malt_bin SET capacity_tonnes = 10.0 WHERE code = 'B04'")
    found = worth_a_look(desk)
    assert any("more than B04 holds today" in item.detail for item in found)
    assert sound(desk)


def test_sqlite_findings_come_first_and_stop_the_rest(book: Book) -> None:
    """Nothing below them is worth reading until they are dealt with."""
    assert faults(book) == sqlite_says(book) or faults(book) == crossing_rules(book)


def test_an_empty_book_has_every_table_holding_nothing(book: Book) -> None:
    empty = tables_holding_nothing(book)
    assert "party" in empty
    assert "schema_version" not in empty


def test_a_stocked_book_has_fewer_empty_tables(desk: Book) -> None:
    assert len(tables_holding_nothing(desk)) < len(tables_holding_nothing_of_a_fresh_book(desk))


def tables_holding_nothing_of_a_fresh_book(desk: Book) -> tuple[str, ...]:
    """Every table there is, which is what a fresh book has empty."""
    return tuple(table for table in desk.tables() if table != "schema_version")


def test_the_summary_counts_all_three(desk: Book) -> None:
    faults_found, odd, empty = summary(desk)
    assert faults_found == 0
    assert odd > 0
    assert empty > 0


def test_a_second_lot_does_not_upset_the_book(desk: Book) -> None:
    a_lot(desk, "L-TWO", "B05", ("LAUR",), "M-TWO")
    assert sound(desk)


def test_a_foreign_key_check_finds_nothing_on_a_good_book(desk: Book) -> None:
    assert sqlite_says(desk) == []


def test_a_rejected_load_in_a_silo_is_a_fault(stocked: Book) -> None:
    stocked.execute("INSERT INTO silo (code, capacity_tonnes) VALUES ('SL1', 400.0)")
    stocked.execute(
        "INSERT INTO delivery (ticket, purchase, party, arrived, gross_kg, tare_kg) "
        "VALUES ('W-1', 'P-2025-014', 'HOLB', '2025-09-18', 43820.0, 15640.0)"
    )
    stocked.execute(
        "INSERT INTO grading (ticket, standard, outcome, net_tonnes, settled_tonnes, graded_on) "
        "VALUES ('W-1', 'malting 2025', 'rejected', 28.18, 0.0, '2025-09-19')"
    )
    stocked.execute(
        "INSERT INTO silo_receipt (silo, ticket, tonnes, moisture, on_day) "
        "VALUES ('SL1', 'W-1', 28.18, 12.4, '2025-09-19')"
    )
    found = crossing_rules(stocked)
    assert any("was rejected and is in a silo" in item.detail for item in found)
