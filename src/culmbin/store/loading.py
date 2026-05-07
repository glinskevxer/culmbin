"""Loading a batch of laboratory results out of a file.

The laboratory sends a spreadsheet on a Monday with forty analyses on it,
and typing forty analyses in one at a time is how three of them end up on
the wrong lot.

**A file loads whole or not at all.** Eighty percent of a file is the worst
possible outcome: the operator cannot tell which twenty percent failed
without reading the whole thing, and running it again duplicates the eighty
that worked. So the file is read and checked in full before anything is
written, and the write is one transaction.

The format is one row per determination rather than one row per analysis.
A column per analyte would be shorter and it would also mean a new analyte
is a new column, and a laboratory that adds one would silently drop it.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from culmbin.errors import ConflictError, ValidationError
from culmbin.model.analytes import analyte
from culmbin.model.enums import Material
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.store.analyses import find_analysis, save_analysis
from culmbin.store.book import Book

COLUMNS = ("reference", "material", "taken", "code", "value")


@dataclass(frozen=True, slots=True)
class Row:
    """One line of a laboratory file, once it has been read."""

    line: int
    reference: str
    material: Material
    taken: dt.date
    result: Result


def _read_row(line: int, raw: dict[str, str]) -> Row:
    """One row, or say which line it was and what was wrong with it."""
    missing = [column for column in COLUMNS if not (raw.get(column) or "").strip()]
    if missing:
        raise ValidationError(f"line {line} has no {', '.join(missing)}")
    reference = raw["reference"].strip()
    try:
        material = Material(raw["material"].strip())
    except ValueError as exc:
        raise ValidationError(
            f"line {line} says the material is {raw['material'].strip()!r}"
        ) from exc
    try:
        taken = dt.date.fromisoformat(raw["taken"].strip())
    except ValueError as exc:
        raise ValidationError(
            f"line {line} has {raw['taken'].strip()!r} where a date goes"
        ) from exc
    code = raw["code"].strip()
    item = analyte(code)
    if item.material is not material:
        raise ValidationError(
            f"line {line} puts a {item.material} determination in a {material} analysis"
        )
    try:
        value = float(raw["value"])
    except ValueError as exc:
        raise ValidationError(f"line {line} has {raw['value']!r} where a number goes") from exc
    return Row(line, reference, material, taken, Result(code, value, item.basis))


def read(path: Path) -> tuple[Row, ...]:
    """Every row of a file, or the first thing wrong with it."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValidationError(f"{path.name} has no header row in it")
        missing = [column for column in COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValidationError(f"{path.name} has no {', '.join(missing)} column")
        return tuple(_read_row(index, raw) for index, raw in enumerate(reader, start=2))


def gather(rows: tuple[Row, ...]) -> tuple[Analysis, ...]:
    """Turn rows into analyses, in the order the references first appear."""
    order: list[str] = []
    held: dict[str, Row] = {}
    results: dict[str, list[Result]] = {}
    for row in rows:
        if row.reference not in held:
            order.append(row.reference)
            held[row.reference] = row
            results[row.reference] = []
        first = held[row.reference]
        if row.material is not first.material or row.taken != first.taken:
            raise ValidationError(
                f"line {row.line} disagrees with line {first.line} about {row.reference}"
            )
        if any(result.code == row.result.code for result in results[row.reference]):
            raise ValidationError(
                f"line {row.line} is the second {row.result.code} for {row.reference}"
            )
        results[row.reference].append(row.result)
    return tuple(
        analysis_of(reference, held[reference].material, held[reference].taken, results[reference])
        for reference in order
    )


def load(book: Book, path: Path, note: str = "") -> tuple[Analysis, ...]:
    """Read a file, check every row, and write the lot in one transaction.

    Nothing is written until every row has been read and every analysis has
    been built, so a file with a bad line on it leaves the book exactly as
    it was.
    """
    analyses = gather(read(path))
    for analysis in analyses:
        if find_analysis(book, analysis.reference) is not None:
            raise ConflictError(
                f"{analysis.reference} is already in the book, so this file is a repeat"
            )
    with book.writing():
        for analysis in analyses:
            save_analysis(book, analysis, note)
    return analyses
