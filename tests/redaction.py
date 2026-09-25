"""How a fixture spells what it redacted, for a leaf that writes a redacted value out in full.

A plain module rather than the conftest: the extractor's leaves and the enrichment prompt's
both spell a task notice's tags this way, and those live in two directories.
"""


def padded(length: int) -> str:
    """A redacted leaf tag's text: `[redacted] ` repeated to the length it was recorded at."""
    return ("[redacted] " * (length // 11 + 1))[:length]
