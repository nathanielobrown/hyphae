"""A URL for every node of a session: the session, a turn, a run, a call, a tool, and the rest.

Five routes for eight kinds, because the four recorded on a thread read at one URL. What a
route does is name the node — a `Ref`, which is a kind and two ids — and the read behind it
takes the rest off that kind's row in `kinds.KINDS`. The two buckets are here as well, a
thread's api calls that answer no turn and the session's runs no tool call spawned, because a
bucket gets a page like anything else (`CONTEXT.md`).

Every one of the five resolves the same way: the URL names a node, `browser.browse` reads it
whole and closes the store, and the markup dependency draws what came back. Only the naming
differs, so only the naming is written five times.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from hyphae.view.components import Html
from hyphae.view.deps import ViewerDep
from hyphae.view.nodes import Kind, Ref
from hyphae.view.pages.node.browser import Missing, browse
from hyphae.view.pages.node.kinds import KINDS
from hyphae.view.pages.node.markup import page as node_page
from hyphae.view.pages.node.models import NodePage
from hyphae.view.pages.node.routes.knobs import KnobsDep, PageDep

router = APIRouter()


def reading(selects: Callable[..., Ref]) -> Callable[..., Html]:
    """The read and the markup behind one node URL, given the dependency that names its node.

    The parameters are ordered the way the refusals are: a knob outside its bounds is a 400
    before the URL is asked whether it names a node at all, and only a node that exists is
    asked for a page number. The five routes refused in that order before they shared a read,
    and share it now without changing which refusal a doubly-wrong URL gets.
    """

    def read(
        viewer: ViewerDep,
        session_id: str,
        knobs: KnobsDep,
        at: Annotated[Ref, Depends(selects)],
        page: PageDep,
    ) -> NodePage:
        """The whole document, read and closed before any of it is drawn."""
        try:
            return browse(viewer.db, session_id, at, knobs, page)
        except Missing as gone:
            raise HTTPException(404, str(gone)) from gone

    def markup(read: Annotated[NodePage, Depends(read)], viewer: ViewerDep) -> Html:
        return node_page.page(read=read, dev=viewer.dev)

    return markup


def session_node(session_id: str) -> Ref:
    """A session's own node: what it was, and its main thread as the NavTree's first level."""
    return Ref(Kind.SESSION, None, session_id)


def thread_node(kind: str, source: str, node_id: str) -> Ref:
    """One node recorded on a thread: a turn, an api call, a tool call, or a compaction.

    `KINDS` is total over `Kind`, so the word alone does not say the URL is one this serves: a
    session, an agent run and the two buckets each read at a path of their own, and answering
    for one here would key its header by a thread it was never recorded on.
    """
    if kind not in set(Kind) or not KINDS[Kind(kind)].in_thread:
        raise HTTPException(404, "No node of that kind is read on a thread.")
    return Ref(Kind(kind), source, node_id)


def run_node(run_id: str) -> Ref:
    """One agent run, whose id is also the `source` its rows carry — hence no thread segment."""
    return Ref(Kind.RUN, run_id, run_id)


def unattributed_node(source: str) -> Ref:
    """One thread's bucket of api calls that answer no turn."""
    return Ref(Kind.UNATTRIBUTED, source, source)


def unattached_node(session_id: str) -> Ref:
    """The session's one bucket of agent runs no spawning call resolved."""
    return Ref(Kind.UNATTACHED, None, session_id)


SessionMarkup = Annotated[Html, Depends(reading(session_node))]
ThreadMarkup = Annotated[Html, Depends(reading(thread_node))]
RunMarkup = Annotated[Html, Depends(reading(run_node))]
UnattributedMarkup = Annotated[Html, Depends(reading(unattributed_node))]
UnattachedMarkup = Annotated[Html, Depends(reading(unattached_node))]


@router.get("/session/{session_id}")
def session_page(page: SessionMarkup, viewer: ViewerDep) -> Response:
    """A session's own node: what it was, and its main thread as the NavTree's first level."""
    return viewer.html(page)


@router.get("/session/{session_id}/thread/{source}/{kind}/{node_id}")
def thread_page(page: ThreadMarkup, viewer: ViewerDep) -> Response:
    """One node recorded on a thread: a turn, an api call, a tool call, or a compaction.

    One route for the four, because a node page is one response and their URLs say the same
    thing — which thread, which kind, which id. What the kind decides is the header read and
    what hangs under it, and that is a row of `KINDS` rather than a route.
    """
    return viewer.html(page)


@router.get("/session/{session_id}/run/{run_id}")
def run_page(page: RunMarkup, viewer: ViewerDep) -> Response:
    """One agent run: the brief it was given, and its own thread of turns."""
    return viewer.html(page)


@router.get("/session/{session_id}/thread/{source}/unattributed")
def unattributed_page(page: UnattributedMarkup, viewer: ViewerDep) -> Response:
    """One thread's api calls that answer no turn — a resume's calls answer turns that
    live in the session it resumed, and this is where they are read."""
    return viewer.html(page)


@router.get("/session/{session_id}/unattached")
def unattached_page(page: UnattachedMarkup, viewer: ViewerDep) -> Response:
    """The session's agent runs no spawning call resolved.

    Session-scoped rather than per thread: what makes a run unattached is that nothing says
    which thread spawned it, so the bucket hangs off the session itself.
    """
    return viewer.html(page)
