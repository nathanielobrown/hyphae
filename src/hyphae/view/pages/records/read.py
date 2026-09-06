"""Reading one page of a thread's raw records out of the store, at the cursor a URL carried.

The whole document from one open of the store, closed before anything renders
(`view/deps.py`, the window trade-off). Nothing above this module names a query, a binding or
a store column.
"""

from pathlib import Path

from hyphae.analyze.queries import ParamValue
from hyphae.view import bounds
from hyphae.view.citation import cited
from hyphae.view.pages.records.models import RecordRow, RecordsPage
from hyphae.view.store import MATCHED_ROWS, Page, bound, open_store, page_rows, paged


def records(db: Path, session_id: str, source: str, after: int, size: int) -> RecordsPage | None:
    """One page of a thread's records, or None where the store holds none at that line.

    A thread the store never held and a cursor past the end of one it does are the same answer
    — nothing at this URL. Neither is a page worth rendering empty.
    """
    keyed: dict[str, ParamValue] = {"session_id": session_id, "source": source}
    binds = bound(Page.RECORDS, bounds.RECORDS_WIDTHS, **keyed, after=after, page_records=size)
    with open_store(db) as connection:
        page = paged(page_rows(connection, Page.RECORDS, **binds), "line_no")
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
                line_no=row["line_no"],
                type=row["type"],
                timestamp=row["timestamp"],
                raw_chars=row["raw_chars"],
                raw_head=row["raw_head"],
            )
            for row in page.rows
        ],
        matched=first[MATCHED_ROWS],
        opened=first["line_no"] if first["raw_chars"] <= bounds.OPENED_RECORD_CHARS else None,
        after=page.after,
        more=page.more,
        size=size,
        citations={Page.RECORDS.value: cited(Page.RECORDS, binds)},
    )
