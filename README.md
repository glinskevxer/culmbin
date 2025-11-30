# culmbin

Record keeping for a malthouse.

Barley comes in on a lorry, gets graded and put in a silo. It is steeped,
germinated, kilned, tested, blended and shipped to brewers and distillers
against contracts signed a year earlier. `culmbin` is the book that records
all of it and the arithmetic that turns it into the numbers somebody is paid
against.

It is a command line tool over a SQLite file. No server and no web UI.

## What it covers

- Barley intake: sampling, grading, the deduction schedule and settlement.
  A rejected load has no settled weight, because the schedule does not apply
  to it.
- New crop is screened on germinative energy as well as capacity, so the
  same sample is a different answer in September and in November.
- Steep programmes, germination on the degree hour clock, and kiln curves.
  Turning points are degree hours, so a cold box gets fewer turns.
- Malt analysis on the right basis, specification conformance, and blend
  prediction on the right weighting for each determination.
- Malt bins with varietal segregation that propagates and does not recover.
- Contracts drawn down in contract tonnes rather than weighbridge tonnes.
- Traceability from a lorry load forward and from a shipment back.

## Getting started

```
pip install -e ".[dev]" -c constraints.txt
culmbin --book book.sqlite3 init
culmbin --book book.sqlite3 status
```

Every command takes `--book` and `--on`. The second one is the day the
command is worked as, and it is the only place a clock enters the package.

```
culmbin --book book.sqlite3 --on 2025-09-18 delivery add W-1 P-1 --party HOLB \
  --gross 43820 --tare 15640 --harvested 2025-08-14
culmbin --book book.sqlite3 delivery waiting
culmbin --book book.sqlite3 report intake
```

## Layout

```
src/culmbin/    the package
tests/          the tests, one directory per package
docs/           three generated documents and one written by hand
```

- `docs/design.md` is the layering and why it is that shape.
- `docs/schema.md` is the book, generated from the migrations.
- `docs/commands.md` is the console script, generated from the click tree.
- `docs/glossary.md` is the words, generated from the enumerations.

## Working on it

```
python -m ruff check . && python -m ruff format --check .
python -m mypy
python -m pytest -q
```

There are self-checks as well, and CI runs every one of them. They read the
source tree with `ast` rather than importing it, because a module that fails
to import is exactly the module worth reporting on.

```
python -m culmbin.tools.check_layers
python -m culmbin.tools.check_wiring
python -m culmbin.tools.check_naming
```

The three generated documents are regenerated and compared in CI, so they
cannot go stale.

```
python -m culmbin.tools.schema_dump --check
python -m culmbin.tools.build_docs --check
python -m culmbin.tools.build_glossary --check
```
