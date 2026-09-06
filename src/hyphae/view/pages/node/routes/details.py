"""The rest of one cut value: what a pane previewed at its width, fetched whole.

Every fat value on a node page is printed to its cut and marked, and the mark links here
(`docs/viewer-bounds.md`). One handler serves all sixteen, because a Detail declares
everything the fetch needs (`view/detail.py:DETAILS`): the query behind it, how it was
written, and the keys its route carries.

One dependency behind each endpoint rather than a read and a markup either side of a typed
seam: what a fetch reads is a single value, and a model carrying one value is the value
(`plans/deepen-viewer-reads/design.md`). What the endpoint never sees is the query, the
bindings or the row — those stop in `pages/node/fragments.py`.

The record route is the exception and keeps its own read: it arrives with a header line of
its own, nothing previews a head of it, and no pane files it under a name.
"""

from collections.abc import Callable, Mapping
from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from hyphae.view.components import Html
from hyphae.view.deps import Db, ViewerDep
from hyphae.view.detail import DETAILS, Spec, Written
from hyphae.view.pages.node import fragments
from hyphae.view.pages.node.browser import Missing
from hyphae.view.pages.node.markup import values

router = APIRouter()


def fetch(spec: Spec, keys: Mapping[str, str], connection: Db) -> Html:
    """One Detail whole, in the block its head was previewed in.

    `Written` decides which of the three blocks the value comes back in; the read decides
    what a value that is not there means, and says the same nothing a missing row does.
    """
    try:
        read = fragments.detailed(connection, spec, keys)
    except Missing as gone:
        raise HTTPException(404, str(gone)) from gone
    match spec.written:
        case Written.LINE:
            return values.enrichment_line(node=read.whole)
        case Written.MARKDOWN:
            return values.prose(node=read.whole)
        case Written.BASH | Written.JSON | Written.NAMED_FILE:
            assert read.syntax is not None  # noqa: S101  # only the two prose arms answer None
            return values.code(node=read.whole, syntax=read.syntax)
        case _:
            assert_never(spec.written)


def serving(spec: Spec) -> Callable[..., Response]:
    """One spec bound into an endpoint FastAPI can read a signature off.

    A closure rather than sixteen stubs: what changes between the routes is the spec, and what
    stays is the fetch behind it and the viewer that answers with what came back. The keys come
    off the request rather than a signature per route: the path named them, and the spec's own
    route template is what minted the URL.
    """

    def fetched(request: Request, connection: Db) -> Html:
        return fetch(spec, request.path_params, connection)

    def serve(value: Annotated[Html, Depends(fetched)], viewer: ViewerDep) -> Response:
        return viewer.html(value)

    return serve


def register(on: APIRouter) -> None:
    """Every Detail the registry declares, as a route of its own on `on`.

    The public URLs are the registry's own, one route each — not one route under a
    `/fragment/{detail}` segment, which would collide with the popover and expansion
    fragments and move the unknown-name 404 out of the router and into the handler.
    """
    for spec in DETAILS:
        on.add_api_route(spec.route, serving(spec), methods=["GET"], name=spec.whole.value)


register(router)


def recorded(session_id: str, source: str, line_no: int, connection: Db) -> Html:
    """One raw transcript record whole, as the browser's preview was cut from.

    Its own renderer rather than a value fragment: a record arrives with a header line of
    its own, and it is the line a node was read from rather than one of the node's values,
    so nothing on a pane files it under a name and nothing swaps it into a detail.
    """
    try:
        return values.record(node=fragments.recorded(connection, session_id, source, line_no))
    except Missing as gone:
        raise HTTPException(404, str(gone)) from gone


@router.get("/fragment/record/session/{session_id}/thread/{source}/line/{line_no}")
def record_value(record: Annotated[Html, Depends(recorded)], viewer: ViewerDep) -> Response:
    """One raw transcript record whole."""
    return viewer.html(record)
