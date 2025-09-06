"""The console script.

One command per thing somebody does, grouped the way the building is
organised rather than the way the package is. The intake office does not
care that a delivery is in `store` and a grading is in `intake`.

Two rules run through the whole of this layer.

**Nothing below the console script knows what day it is.** The clock enters
here, through `--on`, and is passed down as an argument. That is what makes
every rule below testable without freezing time.

**A command prints and returns nothing.** The exit status is the whole of
the machine readable answer, and anything a human needs is on standard
output.
"""

from __future__ import annotations
