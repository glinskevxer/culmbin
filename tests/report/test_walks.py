"""The traceability pages."""

from __future__ import annotations

from culmbin.report.walks import investigation_page, recall_page
from culmbin.store.book import Book


def test_the_recall_page_opens_with_the_customers(chain: Book) -> None:
    text = recall_page(chain, "W-1")
    assert "customers to ring" in text
    assert "BRWY" in text


def test_the_recall_page_names_the_grower_and_the_ticket(chain: Book) -> None:
    text = recall_page(chain, "W-1")
    assert "recall walk from W-1" in text
    assert "grower   HOLB" in text


def test_the_recall_page_lists_what_has_gone_out(chain: Book) -> None:
    text = recall_page(chain, "W-1")
    assert "gone out" in text
    assert "S-1" in text
    assert "L-1" in text


def test_a_load_still_on_site_says_so(chain: Book) -> None:
    chain.execute("DELETE FROM shipment")
    text = recall_page(chain, "W-1")
    assert "none of this barley has left the site." in text
    assert "customers to ring" not in text


def test_the_investigation_page_opens_with_the_growers(chain: Book) -> None:
    text = investigation_page(chain, "S-1")
    assert "growers behind it" in text
    assert "HOLB" in text
    assert "WYKE" in text


def test_the_investigation_page_names_the_customer_and_the_lot(chain: Book) -> None:
    text = investigation_page(chain, "S-1")
    assert "customer    BRWY" in text
    assert "lot         L-1" in text


def test_the_investigation_page_lists_the_pieces_and_their_tickets(chain: Book) -> None:
    text = investigation_page(chain, "S-1")
    assert "2025-118" in text
    assert "W-1, W-2" in text


def test_an_incomplete_walk_says_so_rather_than_looking_empty(chain: Book) -> None:
    """A walk that stopped looks exactly like a walk that found nothing."""
    chain.execute("DELETE FROM piece_source")
    text = investigation_page(chain, "S-1")
    assert "this walk is incomplete" in text
    assert "not recorded" in text


def test_both_pages_end_in_a_newline_and_have_no_trailing_space(chain: Book) -> None:
    for text in (recall_page(chain, "W-1"), investigation_page(chain, "S-1")):
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())
