"""Taking barley in: the standard, the screen, the schedule and settlement.

This layer knows about `model`, `units` and `store`. It is where the rules
about what a load is worth live, and it is deliberately separate from what a
load *is*, because a load is a fact and the rules change every season.
"""

from __future__ import annotations
