"""The pages somebody actually reads.

Every page in this package is text on a fixed width, because the ones that
matter get printed and pinned up in the intake office or handed to a lorry
driver. Nothing here knows how to write to a file: a page is a string and
the caller decides where it goes.
"""

from __future__ import annotations
