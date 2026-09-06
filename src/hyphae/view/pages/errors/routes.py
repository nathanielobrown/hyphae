"""The errors page: every failed tool call of one session, on every thread, in order.

Not a node page: a failure is a property of a tool call rather than a place in the NavTree, and
a session's failures are scattered across every thread it ran (`docs/viewer.md`). Three
dependencies and an adapter, the shape a full document takes: the read opens the store and
closes it, and the 404 is worded here because only an adapter knows what a status is.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from hyphae.view.components import Html
from hyphae.view.deps import ViewerDep
from hyphae.view.pages.errors import markup, read
from hyphae.view.pages.errors.models import ErrorsPage

router = APIRouter()


def errors_read(session_id: str, viewer: ViewerDep) -> ErrorsPage:
    """One session's failures, or the 404 that says which nothing this is."""
    page = read.errors(viewer.db, session_id)
    if not page.listed:
        raise HTTPException(
            404,
            "This session's tool calls all succeeded."
            if page.held
            else "No session with that id is in this store.",
        )
    return page


ErrorsRead = Annotated[ErrorsPage, Depends(errors_read)]


def errors_markup(page: ErrorsRead, viewer: ViewerDep) -> Html:
    """That read, rendered."""
    return markup.errors_page(page=page, dev=viewer.dev)


ErrorsMarkup = Annotated[Html, Depends(errors_markup)]


@router.get("/session/{session_id}/errors")
def errors_page(page: ErrorsMarkup, viewer: ViewerDep) -> Response:
    """Every failed tool call of one session, in the order they happened.

    Not a node page: a failure is a property of a tool call rather than a place in the
    NavTree, and a session's failures are scattered across every thread it ran. So this is a
    list, and each row leads to the tool call's own page — which opens the NavTree at it and
    carries the crumbs that place it.
    """
    return viewer.html(page)
