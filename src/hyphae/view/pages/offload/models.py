"""What the offload page's read hands its markup: one file, and the chunk of it it served.

Neutral by design (`plans/deepen-viewer-reads/design.md`): no request, no response, no element
and no raw store row. The offset is this page's own — a character position in one file, not a
page number — so it crosses the seam beside the chunk it cut.
"""

from collections.abc import Mapping
from typing import NamedTuple

from hyphae.view.citation import Cited


class OffloadFile(NamedTuple):
    """One offloaded tool result as its page prints it, built from its store row."""

    name: str
    size_bytes: int
    content_chars: int
    lossy_decode: bool
    chunk: str


class OffloadPage(NamedTuple):
    """One chunk of one offloaded result, and where the next one starts."""

    session_id: str
    file: OffloadFile
    # Where the next chunk starts, or None where this one reached the end.
    after: int | None
    size: int
    citations: Mapping[str, Cited]
