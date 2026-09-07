"""A child opened in place: the body a log row's View button swaps in, and the rows under it.

An expansion is a node's own body without its page — the same title, facts and details, read
from the same header queries — so a reader can open a child without losing the log they are
reading. What it does not open is another level: a count and a link stand in for one, except
where the level below opens nothing further (`docs/viewer.md`).

Both mounts resolve the way a node page does: the URL names a node, `browser` reads it and
closes the store, and the markup dependency draws what came back. The knobs come along for the
links this serves, not for what it reads — the mount carries the page's own query string so a
reader who opens an expansion and clicks through it keeps the preset and the sizes they were
reading under.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from hyphae.view import bounds, nodes
from hyphae.view.components import Html
from hyphae.view.deps import ViewerDep
from hyphae.view.nodes import Kind, Ref
from hyphae.view.pages.node.browser import Missing, opened, spilled
from hyphae.view.pages.node.kinds import KINDS
from hyphae.view.pages.node.markup import body as node_body
from hyphae.view.pages.node.markup import nav_tree
from hyphae.view.pages.node.models import Expansion, NavTreeRow
from hyphae.view.pages.node.routes.knobs import KnobsDep

router = APIRouter()


def expanding(selects: Callable[..., Ref]) -> Callable[..., Html]:
    """The read and the markup behind one expansion, given the dependency naming its node.

    Ordered the way the refusals are, as the node page's own graph is: a knob outside its
    bounds is a 400 before the URL is asked whether it names a kind that expands at all.
    """

    def read(
        viewer: ViewerDep,
        session_id: str,
        knobs: KnobsDep,
        at: Annotated[Ref, Depends(selects)],
    ) -> Expansion:
        try:
            return opened(viewer.db, session_id, at, knobs.log)
        except Missing as gone:
            raise HTTPException(404, str(gone)) from gone

    def markup(read: Annotated[Expansion, Depends(read)], knobs: KnobsDep) -> Html:
        return node_body.expansion(
            node=read.node,
            facts=read.facts,
            suffix=knobs.suffix,
            shape=read.shape,
            children=read.children,
            rows=read.rows,
            citations=read.citations,
            span=read.span,
        )

    return markup


def thread_node(kind: str, source: str, node_id: str) -> Ref:
    """One node recorded on a thread, for an expansion in its parent.

    `KINDS` is total over `Kind`, so the word alone does not say the URL is one this serves: a
    session, a run and the two buckets each read at a path of their own, and answering for one
    here would key its header by a thread it was never recorded on. Which is the same refusal
    the read gives a kind no log lists, and says the same sentence.
    """
    if kind not in set(Kind) or not KINDS[Kind(kind)].in_thread:
        raise HTTPException(404, "No expansion is served for that kind of node.")
    return Ref(Kind(kind), source, node_id)


def run_node(run_id: str) -> Ref:
    """One agent run. Its own mount: a run's URL carries its id where a thread goes."""
    return Ref(Kind.RUN, run_id, run_id)


ThreadBody = Annotated[Html, Depends(expanding(thread_node))]
RunBody = Annotated[Html, Depends(expanding(run_node))]


@router.get(f"{nodes.BODY_URL}/session/{{session_id}}/thread/{{source}}/{{kind}}/{{node_id}}")
def thread_body(body: ThreadBody, viewer: ViewerDep) -> Response:
    """The body of a turn, an api call, or a tool call, for an expansion in its parent."""
    return viewer.html(body)


@router.get(f"{nodes.BODY_URL}/session/{{session_id}}/{Kind.RUN}/{{run_id}}")
def run_body(body: RunBody, viewer: ViewerDep) -> Response:
    """One agent run's body."""
    return viewer.html(body)


def deep(depth: int) -> int:
    """How deep in the NavTree the rows land, or a 400 — no row of one sits outside it."""
    if not 0 < depth <= bounds.DEPTH:
        raise HTTPException(400, f"A NavTree row sits between depth 1 and {bounds.DEPTH}.")
    return depth


DepthDep = Annotated[int, Depends(deep)]


def spilling(selects: Callable[..., Ref]) -> Callable[..., Html]:
    """The read and the markup behind the rest of one level, given the node it hangs under.

    `thread` is the reader's, not the level's, and neither it nor `depth` has a default: these
    rows are going somewhere in a NavTree that already exists, and only the row that asked for
    them knows where they land and which thread's descriptions it was drawn by.
    """

    def read(
        viewer: ViewerDep,
        session_id: str,
        knobs: KnobsDep,
        at: Annotated[Ref, Depends(selects)],
        thread: str,
        depth: DepthDep,
        opened: str = "",
    ) -> list[NavTreeRow]:
        try:
            return spilled(viewer.db, session_id, at, thread, depth, opened, knobs)
        except Missing as gone:
            raise HTTPException(404, str(gone)) from gone

    def markup(
        read: Annotated[list[NavTreeRow], Depends(read)], knobs: KnobsDep, thread: str
    ) -> Html:
        # The rows arrive with no wrapper of their own: inside the list the tail row was in,
        # each inherits the NavTree's swap from `#nav-tree-rows` like every other row.
        return nav_tree.lines(rows=read, suffix=knobs.suffix, thread=thread)

    return markup


def thread_level(kind: str, source: str, node_id: str) -> Ref:
    """The node a level hangs under, recorded on a thread."""
    if kind not in set(Kind):
        raise HTTPException(404, "No level is served for that kind of node.")
    return Ref(kind=Kind(kind), source=source, node_id=node_id)


def loose_level(kind: str, node_id: str) -> Ref:
    """The node a level hangs under, where it carries no thread of its own.

    The session, an agent run, and the unattached bucket: their URLs have no room for the
    thread the node was recorded on, and the level does not need it — each builder reads the
    thread out of the node it hangs under.
    """
    if kind not in set(Kind):
        raise HTTPException(404, "No level is served for that kind of node.")
    return Ref(kind=Kind(kind), source=None, node_id=node_id)


ThreadKin = Annotated[Html, Depends(spilling(thread_level))]
LooseKin = Annotated[Html, Depends(spilling(loose_level))]


@router.get(f"{nodes.KIN_URL}/session/{{session_id}}/thread/{{source}}/{{kind}}/{{node_id}}")
def node_kin(rows: ThreadKin, viewer: ViewerDep) -> Response:
    """The rest of one level, under a node recorded on a thread."""
    return viewer.html(rows)


@router.get(f"{nodes.KIN_URL}/session/{{session_id}}/{{kind}}/{{node_id}}")
def loose_kin(rows: LooseKin, viewer: ViewerDep) -> Response:
    """The rest of one level, under a node that carries no thread of its own."""
    return viewer.html(rows)
