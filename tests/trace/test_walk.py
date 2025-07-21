"""The traceability walks, both ways along the same chain."""

from __future__ import annotations

import pytest

from culmbin.errors import NotFoundError
from culmbin.model.enums import ShipmentState
from culmbin.store.book import Book
from culmbin.store.shipments import advance
from culmbin.trace.walk import (
    backward_from_shipment,
    customers_affected,
    forward_from_delivery,
    growers_behind,
    piece_sources_missing,
)


def test_a_lorry_reaches_the_customer_it_ended_up_with(chain: Book) -> None:
    walk = forward_from_delivery(chain, "W-1")
    assert walk.grower == "HOLB"
    assert walk.pieces == ("2025-118", "2025-119")
    assert walk.bins == ("B04",)
    assert walk.lots == ("L-1",)
    assert walk.customers == ("BRWY",)
    assert walk.reached_a_customer
    assert not walk.still_ours


def test_both_lorries_reach_the_same_customer(chain: Book) -> None:
    """They went into the same silo, so they are in the same pieces."""
    assert forward_from_delivery(chain, "W-2").customers == ("BRWY",)


def test_a_cancelled_shipment_is_not_on_the_forward_walk(chain: Book) -> None:
    chain.execute("UPDATE shipment SET state = 'planned' WHERE code = 'S-1'")
    advance(chain, "S-1", ShipmentState.CANCELLED)
    walk = forward_from_delivery(chain, "W-1")
    assert walk.shipments == ()
    assert walk.customers == ()
    assert walk.still_ours


def test_a_lorry_that_has_gone_nowhere_is_still_ours(chain: Book) -> None:
    chain.execute("DELETE FROM piece_source WHERE ticket = 'W-1'")
    walk = forward_from_delivery(chain, "W-1")
    assert walk.pieces == ()
    assert walk.still_ours


def test_a_lorry_that_is_not_there_is_refused(chain: Book) -> None:
    with pytest.raises(NotFoundError):
        forward_from_delivery(chain, "W-9")


def test_a_shipment_walks_back_to_both_growers(chain: Book) -> None:
    walk = backward_from_shipment(chain, "S-1")
    assert walk.customer == "BRWY"
    assert walk.lot == "L-1"
    assert walk.pieces == ("2025-118", "2025-119")
    assert walk.tickets == ("W-1", "W-2")
    assert walk.growers == ("HOLB", "WYKE")
    assert walk.complete


def test_a_walk_that_stops_at_the_steep_says_so(chain: Book) -> None:
    """It looks like an answer, which is why it is asked rather than noticed."""
    chain.execute("DELETE FROM piece_source")
    walk = backward_from_shipment(chain, "S-1")
    assert walk.tickets == ()
    assert not walk.complete


def test_a_shipment_that_is_not_there_is_refused(chain: Book) -> None:
    with pytest.raises(NotFoundError):
        backward_from_shipment(chain, "S-9")


def test_the_recall_list_is_the_customers(chain: Book) -> None:
    assert customers_affected(chain, "W-1") == ("BRWY",)


def test_the_investigation_list_is_the_growers(chain: Book) -> None:
    assert growers_behind(chain, "S-1") == ("HOLB", "WYKE")


def test_a_piece_with_sources_is_not_missing_them(chain: Book) -> None:
    assert not piece_sources_missing(chain, "2025-118")


def test_a_piece_with_no_sources_is_missing_them(chain: Book) -> None:
    chain.execute("DELETE FROM piece_source WHERE piece = '2025-118'")
    assert piece_sources_missing(chain, "2025-118")


def test_asking_about_a_piece_that_is_not_there_is_refused(chain: Book) -> None:
    with pytest.raises(NotFoundError):
        piece_sources_missing(chain, "2025-999")


def test_the_two_walks_meet_in_the_middle(chain: Book) -> None:
    """Forwards from a lorry and back from the shipment name the same lot."""
    forward = forward_from_delivery(chain, "W-1")
    backward = backward_from_shipment(chain, "S-1")
    assert backward.lot in forward.lots
    assert forward.ticket in backward.tickets
