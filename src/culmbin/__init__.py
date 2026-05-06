"""Record keeping for a malthouse.

The package is layered. `units` converts and knows nothing else, `model`
holds the records, `store` writes them down, and the working packages above
those do one stage of the malthouse each. Nothing in a lower layer imports
from a higher one, which is checked rather than asserted here.
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
