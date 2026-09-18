"""Reading one session's failures out of the store, and whether the session is there at all.

The whole document from one open of the store, closed before anything renders
(`view/deps.py`, the window trade-off). Nothing above this module names a query, a binding or
a store column.
"""

from pathlib import Path

from hyphae.store.handle import open_store
from hyphae.store.pages import Page, page_rows
from hyphae.store.trace_store import PAGE_WAIT
from hyphae.view import bounds, failures
from hyphae.view.bounds import bound
from hyphae.view.citation import cited
from hyphae.view.pages.errors.models import ErrorsPage


def errors(db: Path, session_id: str) -> ErrorsPage:
    """Every failed tool call of one session, in the order they happened."""
    with open_store(db, read_only=True, wait=PAGE_WAIT) as store:
        failed = failures.failures(store, session_id)
        # A session the store never held and one whose calls all succeeded are both nothing at
        # this URL, and not the same nothing. The header is read only when there is a 404 to
        # word, so the page a reader actually opens runs one query.
        held = bool(failed.listed) or bool(
            page_rows(
                store,
                Page.SESSION_HEADER,
                **bound(Page.SESSION_HEADER, bounds.HEADER_WIDTHS, session_id=session_id),
            )
        )
    return ErrorsPage(
        session_id=session_id,
        listed=failed.listed,
        cut=failed.cut,
        held=held,
        citations={citation.name: cited(citation) for citation in failed.ran},
    )
