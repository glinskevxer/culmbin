"""Reading and writing analyses.

An analysis is written down once. A result can be added to one that is
already there, because the lab reports in batches and the moisture comes
back an hour before the extract. A result that is already there cannot be
changed.

That is the rule worth stating plainly: **an analysis is corrected by
issuing another one**, not by editing this one. Somewhere there is a
certificate quoting the first set of numbers, and a book that quietly
changed underneath it cannot explain itself. The reference on the new
analysis is what ties the two together, and the old one stays exactly as it
was sent.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Basis, Material
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.store.book import Book
from culmbin.store.rows import (
    as_date,
    as_enum,
    as_number,
    as_optional_text,
    as_text,
    date_text,
)


def _result(row: sqlite3.Row) -> Result:
    """Turn a row into a result."""
    basis = as_optional_text(row, "basis")
    return Result(
        code=as_text(row, "code"),
        value=as_number(row, "value"),
        basis=None if basis is None else Basis(basis),
    )


def _results(book: Book, reference: str) -> list[Result]:
    """Every result of one analysis, in the order they were written."""
    rows = book.query(
        "SELECT code, value, basis FROM result WHERE analysis = ? ORDER BY rowid",
        (reference,),
    )
    return [_result(row) for row in rows]


def save_analysis(book: Book, analysis: Analysis, note: str = "") -> Analysis:
    """Write a whole analysis, results and all, in one go."""
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO analysis (reference, material, taken, note) VALUES (?, ?, ?, ?)",
            (analysis.reference, analysis.material, date_text(analysis.taken), note),
        )
        writing.executemany(
            "INSERT INTO result (analysis, code, value, basis) VALUES (?, ?, ?, ?)",
            [
                (analysis.reference, result.code, result.value, result.basis)
                for result in analysis.results
            ],
        )
    return analysis


def add_result(book: Book, reference: str, result: Result) -> Analysis:
    """Add one result to an analysis that is already there.

    Refuses to overwrite. The lab reports in batches and a second figure for
    the same analyte means either a retest, which gets its own analysis, or
    a transcription mistake, which nobody wants written over the first one.
    """
    analysis = get_analysis(book, reference)
    if result.code in analysis:
        raise ConflictError(
            f"{reference} already has a {result.label} result, "
            f"so a second one needs its own analysis"
        )
    book.execute(
        "INSERT INTO result (analysis, code, value, basis) VALUES (?, ?, ?, ?)",
        (reference, result.code, result.value, result.basis),
    )
    return get_analysis(book, reference)


def get_analysis(book: Book, reference: str) -> Analysis:
    """One analysis, or say which one was asked for."""
    row = book.first(
        "SELECT reference, material, taken FROM analysis WHERE reference = ?", (reference,)
    )
    if row is None:
        raise NotFoundError(f"no analysis called {reference!r}")
    return analysis_of(
        as_text(row, "reference"),
        as_enum(row, "material", Material),
        as_date(row, "taken"),
        _results(book, reference),
    )


def find_analysis(book: Book, reference: str) -> Analysis | None:
    """One analysis, or nothing."""
    try:
        return get_analysis(book, reference)
    except NotFoundError:
        return None


def analysis_note(book: Book, reference: str) -> str:
    """Whatever the lab wrote alongside the numbers."""
    row = book.first("SELECT note FROM analysis WHERE reference = ?", (reference,))
    if row is None:
        raise NotFoundError(f"no analysis called {reference!r}")
    return as_text(row, "note")


def list_analyses(
    book: Book,
    material: Material | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> tuple[Analysis, ...]:
    """Every analysis, oldest first, narrowed by material and by day."""
    clauses = []
    params: list[object] = []
    if material is not None:
        clauses.append("material = ?")
        params.append(material)
    if since is not None:
        clauses.append("taken >= ?")
        params.append(date_text(since))
    if until is not None:
        clauses.append("taken <= ?")
        params.append(date_text(until))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.query(
        f"SELECT reference FROM analysis{where} ORDER BY taken, reference",
        params,
    )
    return tuple(get_analysis(book, as_text(row, "reference")) for row in rows)


def count_analyses(book: Book, material: Material | None = None) -> int:
    """How many analyses the book holds."""
    if material is None:
        return int(book.scalar("SELECT count(*) FROM analysis") or 0)
    return int(book.scalar("SELECT count(*) FROM analysis WHERE material = ?", (material,)) or 0)
