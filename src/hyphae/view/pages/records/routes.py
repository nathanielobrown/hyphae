"""The records page: one page of a thread's raw transcript — where a report's citation lands.

A citation names `(session_id, source, line_no)`; the URL for it is this path with
`?after={line_no - 1}#L{line_no}`, so the cited record is the first row on the page. Three
dependencies and an adapter, the shape a full document takes: the cursor and the size are
checked here, the read opens the store and closes it, and the 404 is worded here.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from hyphae.analyze import queries
from hyphae.view import bounds
from hyphae.view.components import Html
from hyphae.view.deps import ViewerDep, checked
from hyphae.view.pages.records import markup, read
from hyphae.view.pages.records.models import RecordsPage

router = APIRouter()


def records_read(
    session_id: str,
    source: str,
    viewer: ViewerDep,
    after: int = queries.FIRST_PAGE,
    size: int = bounds.RECORDS.default,
) -> RecordsPage:
    """One page of a thread's records, or the 404 that says the store holds none there."""
    page = read.records(viewer.db, session_id, source, after, checked(size, bounds.RECORDS.ceiling))
    if page is None:
        raise HTTPException(404, "This store holds no records for that thread at that line.")
    return page


RecordsRead = Annotated[RecordsPage, Depends(records_read)]


def records_markup(page: RecordsRead, viewer: ViewerDep) -> Html:
    """That read, rendered."""
    return markup.records_page(page=page, dev=viewer.dev)


RecordsMarkup = Annotated[Html, Depends(records_markup)]


@router.get("/session/{session_id}/thread/{source}/records")
def records_page(page: RecordsMarkup, viewer: ViewerDep) -> Response:
    """One page of a thread's raw transcript — where a report's citation lands.

    A citation names `(session_id, source, line_no)`; the URL for it is this path with
    `?after={line_no - 1}#L{line_no}`, so the cited record is the first row on the page.
    """
    return viewer.html(page)
