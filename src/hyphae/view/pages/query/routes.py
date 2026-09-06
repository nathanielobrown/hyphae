"""The query page: one library query's SQL, where every citation in a footer goes.

The name is a key of the query manifest and never a path, which is what makes a request for
`../../secret` a miss rather than a file (`docs/viewer.md`). Three dependencies and an adapter,
the shape a full document takes — this one reads the query library rather than the store, and
the request's own query string crosses the seam as the bindings the citation carried.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from hyphae.view.citation import QUERY_URL
from hyphae.view.components import Html
from hyphae.view.deps import ViewerDep
from hyphae.view.pages.query import markup, read
from hyphae.view.pages.query.models import QueryPage

router = APIRouter()


def query_read(request: Request, query_name: str) -> QueryPage:
    """One library query, or the 404 that says no such query ships with this build."""
    page = read.query(query_name, dict(request.query_params))
    if page is None:
        raise HTTPException(404, "No query by that name ships with this build.")
    return page


QueryRead = Annotated[QueryPage, Depends(query_read)]


def query_markup(page: QueryRead, viewer: ViewerDep) -> Html:
    """That read, rendered."""
    return markup.query_page(page=page, dev=viewer.dev)


QueryMarkup = Annotated[Html, Depends(query_markup)]


@router.get(f"{QUERY_URL}/{{query_name}}")
def query_page(page: QueryMarkup, viewer: ViewerDep) -> Response:
    """One library query's SQL, under the bindings a page cited it with.

    Where every citation in a footer goes. The name is a key of the query manifest and never
    a path: a name the manifest does not declare is a 404 before anything is read, which is
    what makes a request for `../../secret` a miss rather than a file.
    """
    return viewer.html(page)
