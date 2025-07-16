"""Selling malt: allocating it, loading it, sending it and certifying it.

This layer is where the four things a lot has to satisfy meet each other. It
has to be certified, it has to meet the specification the customer signed,
it has to declare the variety the contract names, and there has to be enough
of it left. None of those four belongs to any one record, which is why they
are checked here and only here.
"""

from __future__ import annotations
