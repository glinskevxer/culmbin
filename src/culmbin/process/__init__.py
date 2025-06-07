"""The three stages: steeping, germination and kilning.

Each has a schedule that says what should happen and a set of readings that
say what did. The two are reconciled at the end of the stage and not before,
because a piece that is behind at hour twelve is very often on target at
hour thirty six and nobody should be intervening on the strength of one
reading.
"""

from __future__ import annotations
