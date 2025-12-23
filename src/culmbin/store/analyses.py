"""Reading and writing analyses.

An analysis is written down once. A result can be added to one that is
already there, because the lab reports in batches and the moisture comes
back an hour before the extract. A result that is already there cannot be
changed.

That is the rule worth stating plainly: **an analysis is corrected by
issuing another one**, not by editing this one. Somewhere there is a
certificate quoting the first set of numbers, and a book that quietly
changed underneath it cannot explain itself.

A retest says what it replaces. `supersede` writes the link, and the old
analysis stays exactly as it was sent, still readable, still quotable, and
now findable from the one that replaced it. Anything that would ship malt
on a superseded analysis has to say so, because a certificate quoting
numbers the laboratory has withdrawn is worse than no certificate at all.

A given analysis can be superseded once. A second retest supersedes the
first retest, which is a chain, and a chain has an end that `current` finds.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Basis, Material
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.store.book import Book
from culmbin.store.query import narrowing, optional
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


def supersede(book: Book, old: str, analysis: Analysis, note: str = "") -> Analysis:
    """Write a retest and say which analysis it replaces.

    Refuses to supersede something already superseded: the second retest
    replaces the first retest, not the original, and getting that wrong
    makes two analyses both claim to be current.
    """
    replaced = get_analysis(book, old)
    if analysis.reference == old:
        raise ConflictError(f"{old} cannot supersede itself")
    if analysis.material is not replaced.material:
        raise ConflictError(
            f"{analysis.reference} is a {analysis.material} analysis "
            f"and {old} is a {replaced.material} one"
        )
    existing = superseded_by(book, old)
    if existing is not None:
        raise ConflictError(f"{old} was already superseded by {existing}")
    with book.writing() as writing:
        save_analysis(book, analysis, note)
        writing.execute(
            "UPDATE analysis SET supersedes = ? WHERE reference = ?",
            (old, analysis.reference),
        )
    return analysis


def superseded_by(book: Book, reference: str) -> str | None:
    """The retest that replaced an analysis, or nothing."""
    row = book.first("SELECT reference FROM analysis WHERE supersedes = ?", (reference,))
    return None if row is None else as_text(row, "reference")


def supersedes(book: Book, reference: str) -> str | None:
    """What an analysis replaced, or nothing if it replaced nothing."""
    row = book.first("SELECT supersedes FROM analysis WHERE reference = ?", (reference,))
    if row is None:
        raise NotFoundError(f"no analysis called {reference!r}")
    return as_optional_text(row, "supersedes")


def is_superseded(book: Book, reference: str) -> bool:
    """Whether the laboratory has withdrawn an analysis in favour of a retest."""
    return superseded_by(book, reference) is not None


def current(book: Book, reference: str) -> str:
    """The newest analysis in a retest chain, which may be this one.

    Walks forward. A chain is short in practice and the walk is bounded by
    the number of analyses in the book, so a loop written by something other
    than this package cannot hang it.
    """
    seen = {reference}
    latest = reference
    while True:
        following = superseded_by(book, latest)
        if following is None or following in seen:
            return latest
        seen.add(following)
        latest = following


def chain_of(book: Book, reference: str) -> tuple[str, ...]:
    """The whole retest chain an analysis is in, oldest first."""
    oldest = reference
    seen = {reference}
    while True:
        earlier = supersedes(book, oldest)
        if earlier is None or earlier in seen:
            break
        seen.add(earlier)
        oldest = earlier
    out = [oldest]
    while True:
        following = superseded_by(book, out[-1])
        if following is None or following in out:
            break
        out.append(following)
    return tuple(out)


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
    return optional(lambda: get_analysis(book, reference))


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
    narrow = narrowing().maybe("material = ?", material).since("taken", since)
    narrow.until("taken", until)
    rows = book.query(
        f"SELECT reference FROM analysis{narrow.where} ORDER BY taken, reference",
        narrow.values,
    )
    return tuple(get_analysis(book, as_text(row, "reference")) for row in rows)


def count_analyses(book: Book, material: Material | None = None) -> int:
    """How many analyses the book holds."""
    if material is None:
        return int(book.scalar("SELECT count(*) FROM analysis") or 0)
    return int(book.scalar("SELECT count(*) FROM analysis WHERE material = ?", (material,)) or 0)
