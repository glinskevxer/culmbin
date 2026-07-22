# How culmbin is put together

This is the layering and why it is that shape. The words are in
`docs/glossary.md`, the book is in `docs/schema.md` and the console script
is in `docs/commands.md`, and all three of those are generated. This one is
written by hand, because a design note that could be generated would not be
saying anything.

## The layers

```
units      conversions only, imports nothing but errors
model      enumerations and records, imports units
store      the sqlite book, its migrations and the registers
intake     sampling, grading, the deduction schedule, settlement
process    steep, germination, kiln, and the weight balance
blend      what several lots would assay if they were run together
sales      contracts, call-offs, shipments and certificates
trace      genealogy in both directions
report     the pages somebody actually reads
cli        the console script
tools      the self-checks and the document generators
```

The table is in `culmbin.tools.check_layers` and it is checked on every
build, so this list is a description of something enforced rather than a
promise.

`store` is allowed to reach up into `intake` and `process` for the records
they own. That is the one place the layering bends, and it bends because an
intake standard and a steep programme are values belonging to those
packages that this one writes down.

## What each layer is for

**`units`** is where a number stops being a number. Weight and moisture,
the degree hour clock, the analytical scales, and the two years a malthouse
works in. Everything in it is a function of its arguments: no state, no
book, no clock.

**`model`** is the vocabulary and the records. A `Result` carries a basis, an
`Analysis` converts its own results using its own moisture, and a
`Specification` is a list of clauses that knows how to assess one. Nothing
here reads or writes anything.

**`store`** is the book. One `Book` class, a list of migrations that only
ever grows, and a module per register. The transaction rules live in one
place and so does every statement.

**`intake`**, **`process`**, **`blend`**, **`sales`** and **`trace`** are the
five things the building does. Each has a module of rules and, where the
rules need several tables at once, a desk module that is the only thing
above it anybody calls.

`sales` may import from `process`, which is the one dependency between the
five. Malt comes off the plant and is then sold, so the sales desk asking
what is on the floor is asking a question of something below it.

**`report`** turns records into pages. `culmbin.report.layout` knows nothing
about malt, which is what makes every page above it testable.

**`cli`** is where the clock enters the package, and the only place. That is
checked too, in `culmbin.tools.check_clock`.

**`tools`** is the self-checks and the three document generators. Every
check reads the source tree with `ast` rather than importing it, because a
module that fails to import is exactly the module worth reporting on. CI
runs every one of them, and `culmbin.tools.check_workflow` is what says so.

## The rules that decide what other rules measure

These are the reason the package is not a set of tables with forms over it.

- **Every result carries a basis**, and converting one needs the moisture
  from the same analysis. So `culmbin.model.results.Analysis.value_on` takes
  the basis wanted and does the conversion itself, and nothing anywhere else
  is allowed to.
- **A ratio does not blend.** The Kolbach index of a blend is the blended
  soluble protein over the blended total, which is not the mean of the
  indices. `culmbin.blend.rules` is the table that says which rule each
  determination follows.
- **A rejection is not the bottom of the deduction schedule.** A rejected
  load has no settled weight and no adjustments, and asking what it would
  have been worth raises rather than answering.
- **The germination clock is degree hours.** Turning points are on the same
  clock, so a cold box gets fewer turns and not more.
- **Colour is heat and water together.** A kiln that dries hard before it
  cures makes pale malt on a curve that has not changed.
- **Segregation propagates and does not recover.** A bin that has held two
  varieties is a mixed bin until somebody cleans it out, and a lot drawn
  from it has no variety to declare.
- **The contract tonne is a moisture tonne.** Drier malt draws a contract
  down by more than it weighs.

## What is deliberately not here

No brewing, no farm agronomy, no general ledger and no process control. The
package records what the plant did and works out what it is worth. It does
not drive a valve and it does not post a journal.
