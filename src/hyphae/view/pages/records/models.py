"""What the records page's read hands its markup: one page of a thread's raw transcript.

Neutral by design (`plans/deepen-viewer-reads/design.md`): no request, no response, no element
and no raw store row. The cursor is this page's own — a line number, not a page number — so it
crosses the seam beside the rows it cut.
"""

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from hyphae.view.citation import Cited


class RecordRow(NamedTuple):
    """One archived transcript line as the records page prints it, built from its store row."""

    line_no: int
    type: str
    timestamp: dt.datetime | None
    raw_chars: int
    raw_head: str


class RecordsPage(NamedTuple):
    """One page of one thread's records, and where the next one starts."""

    session_id: str
    source: str
    rows: Sequence[RecordRow]
    # How many records the cursor had ahead of it, counted before the page cut them.
    matched: int
    # The one row that arrives open — the record a citation named — or None where it is too
    # wide to open unasked (`bounds.OPENED_RECORD_CHARS`).
    opened: int | None
    # The line the next page starts after, or None where this page reached the end.
    after: int | None
    more: int
    size: int
    citations: Mapping[str, Cited]
