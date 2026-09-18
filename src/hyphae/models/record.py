"""What the records browser and the offload page read: one raw transcript line as a browser
row previews it and as its fragment prints it whole, and one chunk of a tool result Claude
Code wrote to a file.

Each is built by column name off the statement that answers it (`store/records.py`,
`store/offloads.py`), under `row.ROW`, so a column the statement gains or loses raises at the
read. `Paged` carries beside the rows what a keyset page prints: how many lines the cut left
behind, where the next page resumes, and the citation a footer quotes.
"""

import datetime as dt
from typing import NamedTuple

from pydantic.dataclasses import dataclass

from hyphae.models.citation import Citation
from hyphae.models.row import ROW


@dataclass(frozen=True, config=ROW)
class RecordFields:
    """What every read of one archived transcript line carries: where it sits, what it is."""

    line_no: int
    # What Claude Code stamped the record with, where it did: a `mode` line carries neither.
    uuid: str | None
    type: str
    timestamp: dt.datetime | None
    # The record's true length, beside whatever of the text the read carries.
    raw_chars: int


@dataclass(frozen=True, config=ROW)
class Record(RecordFields):
    """One archived transcript line as the records browser previews it: a `view_records` row."""

    raw_head: str
    # How many records the cursor had ahead of it before the cut, on every row alike.
    matched_rows: int


@dataclass(frozen=True, config=ROW)
class WholeRecord(RecordFields):
    """One archived transcript line whole, as the browser's preview was cut from it: the
    `view_record` row, cited."""

    raw: str
    citation: Citation


class Paged(NamedTuple):
    """One keyset page of a thread's records, and where the next one starts.

    A citation names a line, so the page for it is the one that *starts* at that line rather
    than the nth page of the thread — which is why the cursor is a line number.
    """

    rows: list[Record]
    # How many records the cut left behind, for the "+N more" the page shows instead of losing them.
    more: int
    # The `after` cursor the next page binds, or None when this page is the last.
    after: int | None
    citation: Citation


@dataclass(frozen=True, config=ROW)
class Offload:
    """One offloaded tool result and the chunk of it served: a `view_offload` row, cited."""

    # The transcript's own file name: a key into the store, never a path the server opens.
    name: str
    lossy_decode: bool
    # What was on disk, beside the characters it decoded to — the chunks are characters.
    size_bytes: int
    content_chars: int
    chunk: str
    citation: Citation
