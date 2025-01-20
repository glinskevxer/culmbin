"""The exceptions the package raises.

Every failure a caller can reasonably do something about is one of these.
They all carry a plain sentence, because most of them end up in front of an
intake weighbridge operator rather than a programmer.
"""

from __future__ import annotations


class CulmbinError(Exception):
    """Base class for everything this package raises deliberately."""


class ValidationError(CulmbinError):
    """A value was outside what the field is allowed to hold.

    Raised before anything is written down. The message names the field and
    the bound it broke, so the caller can put the cursor back in the right
    box.
    """


class BasisError(CulmbinError):
    """A number on one moisture basis was used where the other was meant.

    This is separate from `ValidationError` because it is never a typing
    mistake. It means two correct numbers were compared without converting
    one of them.
    """


class NotFoundError(CulmbinError):
    """A record was asked for by a key nothing holds."""


class ConflictError(CulmbinError):
    """The book already holds something that stops this from being written.

    A duplicate delivery note, a vessel that is already occupied, a bin
    receipt that would break segregation.
    """


class StateError(CulmbinError):
    """The record exists and is in the wrong state for what was asked.

    Casting off a piece that has not been steeped, shipping against a
    contract that is closed, correcting an analysis that has been certified.
    """


class SegregationError(CulmbinError):
    """A movement would put two things together that must stay apart."""
