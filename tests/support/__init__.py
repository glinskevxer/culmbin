"""Builders the tests share.

These are here because five test files had grown their own copy of the same
barley sample and they had drifted apart: two of them had a germinative
energy result and three did not, so the same helper name meant two different
things depending on which file you were reading.

Nothing in here asserts anything. It builds records, and every default is a
value that passes, so a test that wants a failure overrides exactly the one
thing it is about and the reader can see what that is.
"""

from __future__ import annotations
