# culmbin

Everything that changed, newest first. A version is cut when the schema
changes or when something the office relies on changes shape, and not on a
timetable.

## 0.5.0

Schema version 21, unchanged. Nothing in the book moved.

- The walk that runs against the installed wheel goes the whole way now.
  It used to stop at the intake settlement, which is one package out of
  nine, and the ones it never reached are the ones with the arithmetic in
  them. It now tips into a silo, charges a piece, casts it, kilns it, bins
  it, seals and certifies a lot, allocates it against a contract, loads a
  lorry and walks the shipment back to the grower it came from.
- That is the difference between knowing a wheel imports and knowing a
  wheel works. Two of the packages it now touches have no code at all in
  the console script walk that CI runs beside it.

## 0.4.0

Schema version 21. One table, for the water meter.

- Steep water. What went over the barley, what the barley kept, and what
  went to drain, which are three numbers and only the last one is what the
  effluent bill is on.
- A piece can be metered as soon as it is cast, because the split into kept
  and drained needs the steep-out moisture and nothing else. The figure per
  tonne of malt waits for a malt weight.

## 0.3.0

Schema version 20. One migration, and it is indexes only: no table changes
and nothing to migrate back out of.

- Fourteen foreign keys had nothing indexing the column they point from.
  SQLite indexes the column being pointed *at*, and every join and every
  cascade in this package goes the other way, so all fourteen were scans.
  On a small book nobody would notice; on a season's worth the reports go
  from a second to a minute.
- A new check, `culmbin.tools.check_indexes`, builds a book from the
  migrations and reads the schema out of it, so the rule is enforced against
  the schema that ships rather than against a list somebody wrote down.
- A batch of laboratory results can be loaded out of a file, whole or not at
  all.
- Grower statements, the barley grading page and the month end balance.

## 0.2.0

Schema version 19, which is six migrations on from 0.1.0. Take a backup
before upgrading: the journal in migration 19 carries triggers, and a book
that is downgraded afterwards will not have them.

- The barley yard. Silos between the weighbridge and the steep, with the
  same segregation rule as the malt bins, and a proportional draw: forty
  tonnes out of four hundred carries a tenth of every load in there.
- Charging a piece out of a silo writes the traceability sources by itself,
  and takes the moisture off what is actually in the silo.
- Retests. An analysis can be superseded, the original stays exactly as it
  was sent, and a lot certified on a withdrawn analysis cannot be shipped.
- Customer complaints, with the ones that cannot be walked back counted
  separately from the ones that can.
- The gas meter. Efficiency, which can be compared between runs, kept apart
  from specific energy, which carries the cast moisture with it.
- Cleaning intervals in days and pieces, whichever comes first, and an
  overdue vessel that takes a piece only when somebody says why.
- An append-only journal of what was done and by whom, enforced by triggers
  rather than by good intentions.
- The month end balance, contract cover, the grower's statement, and a
  `culmbin doctor` that asks a book whether it still makes sense.
- Two more self-checks: migrations are fingerprinted so a shipped one cannot
  change, and the README and design note are checked for names that have
  gone.

## 0.1.0

The first version anybody used.

- Barley intake: purchases, deliveries, the rejection screen, the deduction
  schedule and settlement. A rejection is not the bottom of the schedule and
  has no settled weight.
- New crop is screened on germinative energy as well as capacity, which
  means the same sample is a different answer in September and in November.
- The plant: steep programmes, germination on the degree hour clock, kiln
  curves, and the weight balance that gives malting loss and yield.
- Malt bins with varietal segregation that propagates and does not recover,
  lots, certificates of analysis and blend prediction.
- Contracts, call-offs and shipments, drawn down in contract tonnes rather
  than weighbridge tonnes.
- Traceability both ways, from a lorry load forward and from a shipment
  back.
- A console script over all of it, and the pages the office reads.
