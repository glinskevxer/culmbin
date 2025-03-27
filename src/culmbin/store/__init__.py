"""The book: a SQLite file, its migrations and the registers over it.

Everything above this layer talks to a `Book` and never to `sqlite3`. That
is not tidiness. It is so that there is one place that knows about the
transaction rules, and one place to look when a write turns out not to have
been written.
"""

from __future__ import annotations
