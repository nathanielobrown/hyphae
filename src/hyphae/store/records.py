"""The records browser's read: one page of a thread's raw transcript, at a keyset cursor.

`RecordRepository` is the seam: the page calls `page` with the thread's keys, the cursor a
URL carried and the width its rows preview at, and reads `Record` models back with the
citation its footer quotes. The paging is here too — the cut is the statement's own LIMIT,
and what it left behind is the count the statement carries on every row — so a page cannot
report "+0 more" for rows it silently dropped.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from hyphae.models.citation import Citation
from hyphae.models.record import Paged, Record
from hyphae.store import library

if TYPE_CHECKING:
    # The handle hands out this repository, and this repository holds the handle: the one cycle
    # the design has, so the name is the checker's only.
    from hyphae.store.handle import Store

# One page of a thread's raw transcript, previewed a record per row: keyset on `line_no`, so
# a citation of line N opens the page that starts at it rather than the nth page.
RECORDS = "view_records"


class RecordRepository:
    """The records browser's read, over one open store: `store.records`.

    Keyword-only, one keyword per key the statement binds, with the surface's widths as one
    mapping (`bounds.RECORDS_WIDTHS._asdict()`); `library.bind` fills what the statement
    declares and refuses the rest. A plain class rather than a dataclass: mutmut skips every
    decorated class, and the handle builds one of these per store anyway.
    """

    def __init__(self, store: "Store") -> None:
        self.store = store

    def page(
        self, *, session_id: str, source: str, after: int, size: int, widths: Mapping[str, int]
    ) -> Paged:
        """The records of one thread after line `after`, `size` at most, and where to resume.

        A thread the store never held and a cursor past the end of one it does are the same
        answer: no rows, nothing behind them, nowhere to resume. The size binds as a key
        rather than a size, so the citation quotes it where the page always has.
        """
        bindings = library.bind(
            RECORDS,
            widths,
            {},
            session_id=session_id,
            source=source,
            after=after,
            page_records=size,
        )
        rows = [Record(**row) for row in library.fetch(self.store, library.load(RECORDS), bindings)]
        # What the LIMIT cut, off the count every row carries; the cursor is the last line
        # shown, and only where something is behind it.
        more = rows[0].matched_rows - len(rows) if rows else 0
        return Paged(rows, more, rows[-1].line_no if more else None, Citation(RECORDS, bindings))
