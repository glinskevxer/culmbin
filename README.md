# culmbin

Record keeping for a malthouse.

Barley comes in on a lorry, gets graded and put in a silo. It is steeped,
germinated, kilned, tested, blended and shipped to brewers and distillers
against contracts signed a year earlier. `culmbin` is the book that records
all of it and the arithmetic that turns it into the numbers somebody is paid
against.

It is a command line tool over a SQLite file. No server and no web UI.

## What it covers

- Barley intake: sampling, grading, the deduction schedule and settlement
- Steep programmes, wet stands and air rests, and water uptake
- Germination on the degree-hour clock, turning and casting off
- Kiln curves, thermal load and off-kiln moisture
- Malt analysis, moisture basis and specification conformance
- Malt bins, varietal segregation and blending
- Contracts, calls, shipments and certificates of analysis
- Genealogy from a delivery note forward and from a shipment back

## Layout

```
src/culmbin/    the package
tests/          the tests, one directory per package
docs/           written by hand or generated, and checked either way
```
