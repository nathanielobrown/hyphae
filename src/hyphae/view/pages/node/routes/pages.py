"""A URL for every node of a session: the session, a turn, a run, a call, a tool, and the rest.

Five routes for eight kinds, because the four recorded on a thread read at one URL. What a
route does is name the node — a `Ref`, which is a kind and two ids — and `browse` reads the
rest off that kind's row in `kinds.KINDS`. The two buckets are here as well, a thread's api
calls that answer no turn and the session's runs no tool call spawned, because a bucket gets a
page like anything else (`CONTEXT.md`).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from hyphae.view.deps import ViewerDep
from hyphae.view.nodes import Kind, Ref
from hyphae.view.pages.node.kinds import KINDS
from hyphae.view.pages.node.routes.browse import browse
from hyphae.view.pages.node.routes.knobs import KnobsDep

router = APIRouter()


@router.get("/session/{session_id}")
def session_page(
    session_id: str,
    viewer: ViewerDep,
    knobs: KnobsDep,
    page: int = 1,
) -> Response:
    """A session's own node: what it was, and its main thread as the NavTree's first level."""
    return browse(viewer, session_id, Ref(Kind.SESSION, None, session_id), knobs, page)


@router.get("/session/{session_id}/thread/{source}/{kind}/{node_id}")
def thread_page(
    kind: str,
    session_id: str,
    source: str,
    node_id: str,
    viewer: ViewerDep,
    knobs: KnobsDep,
    page: int = 1,
) -> Response:
    """One node recorded on a thread: a turn, an api call, a tool call, or a compaction.

    One route for the four, because a node page is one response and their URLs say the same
    thing — which thread, which kind, which id. What the kind decides is the header read and
    what hangs under it, and that is a row of `KINDS` rather than a route.

    `KINDS` is total over `Kind`, so the word alone does not say the URL is one this serves: a
    session, an agent run and the two buckets each read at a path of their own, and answering
    for one here would key its header by a thread it was never recorded on.
    """
    if kind not in set(Kind) or not KINDS[Kind(kind)].in_thread:
        raise HTTPException(404, "No node of that kind is read on a thread.")
    return browse(viewer, session_id, Ref(Kind(kind), source, node_id), knobs, page)


@router.get("/session/{session_id}/run/{run_id}")
def run_page(
    session_id: str,
    run_id: str,
    viewer: ViewerDep,
    knobs: KnobsDep,
    page: int = 1,
) -> Response:
    """One agent run: the brief it was given, and its own thread of turns.

    A run's id is also the `source` its rows carry, which is why the URL needs no thread
    segment and why the enrichment is read at the run.
    """
    return browse(viewer, session_id, Ref(Kind.RUN, run_id, run_id), knobs, page)


@router.get("/session/{session_id}/thread/{source}/unattributed")
def unattributed_page(
    session_id: str,
    source: str,
    viewer: ViewerDep,
    knobs: KnobsDep,
    page: int = 1,
) -> Response:
    """One thread's api calls that answer no turn — a resume's calls answer turns that
    live in the session it resumed, and this is where they are read."""
    return browse(viewer, session_id, Ref(Kind.UNATTRIBUTED, source, source), knobs, page)


@router.get("/session/{session_id}/unattached")
def unattached_page(
    session_id: str,
    viewer: ViewerDep,
    knobs: KnobsDep,
    page: int = 1,
) -> Response:
    """The session's agent runs no spawning call resolved.

    Session-scoped rather than per thread: what makes a run unattached is that nothing says
    which thread spawned it, so the bucket hangs off the session itself.
    """
    return browse(viewer, session_id, Ref(Kind.UNATTACHED, None, session_id), knobs, page)
