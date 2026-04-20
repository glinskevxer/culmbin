"""The page about the book itself: what is in it and what is wrong with it.

Not a page about malt. It is the one somebody prints after restoring a
backup, or when a query has started answering something odd, and it is laid
out for that: what SQLite thinks, then what the rules across tables think,
then what is merely worth a look, then how big everything is.

The empty tables are last and they are not a fault. They are the first thing
anybody wants after a restore, which is why they are on the page at all.
"""

from __future__ import annotations

from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.integrity import faults, tables_holding_nothing, worth_a_look
from culmbin.store.migrations import current_version, latest_version
from culmbin.store.search import counts


def book_page(book: Book) -> str:
    """Everything wrong with a book, and everything in it."""
    wrong = faults(book)
    odd = worth_a_look(book)
    empty = tables_holding_nothing(book)
    return page(
        [
            heading(f"the book at {book.path}"),
            pairs(
                [
                    ("schema", f"{current_version(book)} of {latest_version()}"),
                    ("tables", str(len(book.tables()))),
                    ("faults", str(len(wrong))),
                    ("worth a look", str(len(odd))),
                    ("tables holding nothing", str(len(empty))),
                ]
            ),
            table_block(
                "wrong",
                [Column("about"), Column("what")],
                [[item.kind, item.detail] for item in wrong],
            ),
            ["nothing is wrong with this book."] if not wrong else [],
            table_block(
                "worth a look",
                [Column("about"), Column("what")],
                [[item.kind, item.detail] for item in odd],
            ),
            table_block(
                "what is in it",
                [Column("register"), Column("rows", Align.RIGHT)],
                [[kind, str(total)] for kind, total in counts(book) if total],
            ),
            table_block(
                "holding nothing",
                [Column("table")],
                [[table] for table in empty],
            ),
        ]
    )
