"""The offload page: one chunk of a tool result written to a file instead of the transcript.

The name is the transcript's own file name, so it may hold anything a tool named a file. It is
a key into the store and never a path the server opens (`docs/viewer.md`). Three dependencies
and an adapter, the shape a full document takes: the size and the offset are checked here, the
read opens the store and closes it, and the 404 is worded here.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from hyphae.view import bounds
from hyphae.view.components import Html
from hyphae.view.deps import ViewerDep, checked
from hyphae.view.pages.offload import markup, read
from hyphae.view.pages.offload.models import OffloadPage

router = APIRouter()


def offload_read(
    session_id: str,
    offload_name: str,
    viewer: ViewerDep,
    after: int = 0,
    size: int = bounds.CHUNK.default,
) -> OffloadPage:
    """One chunk of an offloaded result, or the 404 that says the session holds no such file."""
    checked(size, bounds.CHUNK.ceiling)
    # The offset is the file's own bound rather than a size, and refused in its own words: a
    # chunk before the start of a file is a bad ask, not an empty page.
    if after < 0:
        raise HTTPException(400, "Ask for an offset of 0 or more.")
    page = read.offload(viewer.db, session_id, offload_name, after, size)
    if page is None:
        raise HTTPException(404, "No offloaded result of that name is in this session.")
    return page


OffloadRead = Annotated[OffloadPage, Depends(offload_read)]


def offload_markup(page: OffloadRead, viewer: ViewerDep) -> Html:
    """That read, rendered."""
    return markup.offload_page(page=page, dev=viewer.dev)


OffloadMarkup = Annotated[Html, Depends(offload_markup)]


@router.get("/session/{session_id}/offload/{offload_name:path}")
def offload_page(page: OffloadMarkup, viewer: ViewerDep) -> Response:
    """One chunk of a tool result Claude Code wrote to a file beside the transcript.

    The name is the transcript's own file name, so it may hold anything a tool named a file —
    spaces, percent signs, something shaped like a path. It is a key into the store and never
    a path the server opens, which is what makes the shape of it uninteresting.
    """
    return viewer.html(page)
