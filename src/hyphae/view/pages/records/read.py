"""Reading one page of a thread's raw records out of the store, at the cursor a URL carried.

The whole document from one open of the store, closed before anything renders
(`view/deps.py`, the window trade-off). Nothing above this module names a query, a binding or
a store column.
"""

from pathlib import Path

from hyphae.store.handle import open_store
from hyphae.store.trace_store import PAGE_WAIT
from hyphae.view import bounds
from hyphae.view.citation import cited
from hyphae.view.pages.records.models import RecordRow, RecordsPage


def records(db: Path, session_id: str, source: str, after: int, size: int) -> RecordsPage | None:
    """One page of a thread's records, or None where the store holds none at that line.

    A thread the store never held and a cursor past the end of one it does are the same answer
    — nothing at this URL. Neither is a page worth rendering empty.
    """
    with open_store(db, read_only=True, wait=PAGE_WAIT) as store:
        page = store.records.page(
            session_id=session_id,
            source=source,
            after=after,
            size=size,
            widths=bounds.RECORDS_WIDTHS._asdict(),
        )
    if not page.rows:
        return None
    # The one record the page fetches unasked: the first row, which is the one a citation
    # named — but only where a record that wide stays inside a page's budget
    # (`bounds.OPENED_RECORD_CHARS`). Past it the row is where every other row is, one click
    # from its own fetch, because a reader who paged here asked for no such thing.
    first = page.rows[0]
    return RecordsPage(
        session_id=session_id,
        source=source,
        rows=[
            RecordRow(
                line_no=row.line_no,
                type=row.type,
                timestamp=row.timestamp,
                raw_chars=row.raw_chars,
                raw_head=row.raw_head,
            )
            for row in page.rows
        ],
        matched=first.matched_rows,
        opened=first.line_no if first.raw_chars <= bounds.OPENED_RECORD_CHARS else None,
        after=page.after,
        more=page.more,
        size=size,
        citations={page.citation.name: cited(page.citation)},
    )
