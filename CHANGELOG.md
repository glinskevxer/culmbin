# culmbin

Everything that changed, newest first. A version is cut when the schema
changes or when something the office relies on changes shape, and not on a
timetable.

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
