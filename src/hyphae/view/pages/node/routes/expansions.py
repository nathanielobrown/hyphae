"""A child opened in place: the body a log row's View button swaps in, and the rows under it.

An expansion is a node's own body without its page — the same title, facts and details, read
from the same header queries — so a reader can open a child without losing the log they are
reading. What it does not open is another level: a count and a link stand in for one, except
where the level below opens nothing further (`docs/viewer.md`).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from hyphae.analyze.queries import ParamValue
from hyphae.view import bounds, nodes
from hyphae.view.citation import Ran, cited
from hyphae.view.deps import Viewer, ViewerDep
from hyphae.view.enrichment import Descriptions, described
from hyphae.view.nodes import Kind, Ref
from hyphae.view.pages.node import reads
from hyphae.view.pages.node.columns import COLUMNS
from hyphae.view.pages.node.kinds import EXPANDED, KINDS, Log
from hyphae.view.pages.node.knobs import Knobs
from hyphae.view.pages.node.markup import body as node_body
from hyphae.view.pages.node.markup import nav_tree
from hyphae.view.pages.node.markup.nav_tree import NavTreeRow
from hyphae.view.pages.node.nav_tree import Corpus, children, spread, windowed
from hyphae.view.pages.node.routes.knobs import KnobsDep
from hyphae.view.store import (
    Page,
    bound,
    open_store,
    page_rows,
)

router = APIRouter()


def expanded(viewer: Viewer, session_id: str, at: Ref, knobs: Knobs) -> Response:
    """One node's body alone, the way an expansion in someone else's log mounts it.

    The same component the full view's pane renders through, so the two cannot drift apart;
    where the page has the crumbs and prev/next, this has the way to the node's own page.

    The knobs come along for the links this serves, not for what it reads: the mount carries
    the page's own query string so a reader who opens an expansion and clicks through it keeps
    the preset and the sizes they were reading under.
    """
    spec = KINDS[at.kind]
    # A kind no children log lists has no expansion — nothing offers one, and there is no row
    # of anybody's table for it to stand in (`nodes.Node.expansion`). It is the same four kinds
    # a header names, which is what lets this read `titled` without a second answer for None.
    if spec.listed_as is None or spec.titled is None:
        raise HTTPException(404, "No expansion is served for that kind of node.")
    source = str(at.source)
    keyed: dict[str, ParamValue] = {"session_id": session_id, "source": source}
    with open_store(viewer.db) as connection:
        # An expansion prices nothing and lists no runs: every node it builds carries the empty
        # ledger, and what it wants of a corpus is the session it is in and the words a pass
        # wrote. Read for the thread in the URL — which for a run is the run's own id, the
        # source its rows carry — so the title is the one the log row that opened this had.
        corpus = Corpus(
            session_id=session_id,
            held=nodes.NO_LEDGER,
            runs=[],
            described=(
                described(connection, session_id, source)
                if spec.describe is not None
                else Descriptions()
            ),
            source=source,
        )
        found = spec.header(connection, corpus, at, EXPANDED)
        if found is None:
            raise HTTPException(404, spec.missing)
        # The level the expansion lists, where its kind lists one: the first page of it, at the
        # size the reader is reading logs under. Which page is not a question an expansion
        # asks — the way past the first is the link to the node's own page.
        under = (
            spec.log(connection, corpus, at, 1, knobs.log)
            if spec.opens and spec.log is not None
            else Log([], 0, [])
        )
    ran: Ran = [*found.ran, *under.ran]
    if corpus.described.queried:
        ran.append((Page.ENRICHMENT, keyed))
    node = spec.titled(corpus, at, found.row)
    return viewer.html(
        node_body.expansion(
            node=node,
            facts=reads.node_facts(node, found.row),
            suffix=knobs.suffix,
            shape=spec.under,
            # What the full view would have listed, counted: the column beside the row, where
            # the kind has one to count.
            children=found.row[spec.counts] if spec.counts else None,
            rows=under.rows,
            citations={named.value: cited(named, binding) for named, binding in ran},
            # An expansion arrives as a row of the log it opened under, spanning every column
            # that log fills. A kind lists in one shape of log wherever it lists at all, which
            # is what makes the width answerable from the child alone.
            span=len(COLUMNS[spec.listed_as]),
        )
    )


@router.get(f"{nodes.BODY_URL}/session/{{session_id}}/thread/{{source}}/{{kind}}/{{node_id}}")
def thread_body(
    kind: str,
    session_id: str,
    source: str,
    node_id: str,
    viewer: ViewerDep,
    knobs: KnobsDep,
) -> Response:
    """The body of a turn, an api call, or a tool call, for an expansion in its parent.

    `KINDS` is total over `Kind`, so the word alone no longer says the URL is one this serves:
    a session, a run and the two buckets each read at a path of their own, and answering for
    one here would key its header by a thread it was never recorded on.
    """
    if kind not in set(Kind) or not KINDS[Kind(kind)].in_thread:
        raise HTTPException(404, "No expansion is served for that kind of node.")
    return expanded(viewer, session_id, Ref(Kind(kind), source, node_id), knobs)


@router.get(f"{nodes.BODY_URL}/session/{{session_id}}/{Kind.RUN}/{{run_id}}")
def run_body(
    session_id: str,
    run_id: str,
    viewer: ViewerDep,
    knobs: KnobsDep,
) -> Response:
    """One agent run's body. Its own mount: a run's URL carries its id where a thread goes."""
    return expanded(viewer, session_id, Ref(Kind.RUN, run_id, run_id), knobs)


def spilled(
    viewer: Viewer, session_id: str, at: Ref, thread: str, depth: int, opened: str, knobs: Knobs
) -> Response:
    """The children one level's window left out: the rows a `+N more` row stands in for.

    The NavTree draws a window on a level and a tail row saying how many it left out; this
    serves the rest of that level, at the depth the NavTree had reached, so a click can stand
    them where the tail row stood. `opened` is the key of the child the open path descends
    through, which the window keeps wherever in the level it sits — the page sent it so
    that the two halves of one split agree, and this is the half that must not repeat it.

    `thread` is the reader's, not the level's: the enrichment is keyed by thread, so a page
    draws a turn of any other thread by its prompt, and a row served here has to read the
    way the page beside it would have drawn it.

    Unbounded on purpose: what comes back is a level less a window, so a node with ten
    thousand children answers with ten thousand rows.
    """
    if not 0 < depth <= bounds.DEPTH:
        raise HTTPException(400, f"A NavTree row sits between depth 1 and {bounds.DEPTH}.")
    keyed: dict[str, ParamValue] = {"session_id": session_id}
    with open_store(viewer.db) as connection:
        head = page_rows(
            connection,
            Page.SESSION_HEADER,
            **bound(Page.SESSION_HEADER, bounds.HEADER_WIDTHS, session_id=session_id),
        )
        if not head:
            raise HTTPException(404, "No session with that id is in this store.")
        # The NavTree's width, where the node page reads the same query at the log's
        # (`browse.py`): what comes back here is drawn as rows and listed in no children log,
        # so the wider read would fetch three times the string for a surface printing a third
        # of it. Nothing rendered says which was chosen — the row cuts to its own width
        # whatever arrives — so `tests/view/test_bounds__widths.py` is what holds it.
        runs = page_rows(connection, Page.RUNS, **bound(Page.RUNS, bounds.NAV_TREE_WIDTHS, **keyed))
        corpus = Corpus(
            session_id=session_id,
            held=nodes.ledger(session_id, head[0]["cost_usd"] or 0, runs),
            runs=runs,
            described=described(connection, session_id, thread),
            source=thread,
        )
        level = children(connection, corpus, at, knobs.nav, opened or None)
    # Each row shut, and under it whatever a shut row stands: the runs it hides come back
    # with it, the way the page's own rows carry them. None of them is a step of the open
    # path — the cap keeps the child the path descends through inside the window, and this
    # fetch is what it left out.
    #
    # They arrive with no wrapper of their own: inside the list the tail row was in, each
    # inherits the NavTree's swap from `#nav-tree-rows` like every other row.
    return viewer.html(
        nav_tree.lines(
            rows=[
                row
                for node in windowed(level.nodes, knobs.kin, [opened]).cut
                for row in [
                    NavTreeRow(node, depth, selected=False, ancestor=False),
                    *spread(corpus, node, depth + 1),
                ]
            ],
            suffix=knobs.suffix,
            thread=thread,
        )
    )


@router.get(f"{nodes.KIN_URL}/session/{{session_id}}/thread/{{source}}/{{kind}}/{{node_id}}")
def node_kin(
    kind: str,
    session_id: str,
    source: str,
    node_id: str,
    thread: str,
    depth: int,
    viewer: ViewerDep,
    knobs: KnobsDep,
    opened: str = "",
) -> Response:
    """The rest of one level, under a node recorded on a thread.

    Neither `thread` nor `depth` has a default: these rows are going somewhere in a NavTree
    that already exists, and only the row that asked for them knows where they land and
    which thread's descriptions the NavTree around them was drawn by.
    """
    if kind not in set(Kind):
        raise HTTPException(404, "No level is served for that kind of node.")
    at = Ref(kind=Kind(kind), source=source, node_id=node_id)
    return spilled(viewer, session_id, at, thread, depth, opened, knobs)


@router.get(f"{nodes.KIN_URL}/session/{{session_id}}/{{kind}}/{{node_id}}")
def loose_kin(
    kind: str,
    session_id: str,
    node_id: str,
    thread: str,
    depth: int,
    viewer: ViewerDep,
    knobs: KnobsDep,
    opened: str = "",
) -> Response:
    """The rest of one level, under a node that carries no thread of its own.

    The session, an agent run, and the unattached bucket: their URLs have no room for the
    thread the node was recorded on, and the level does not need it — each builder reads
    the thread out of the node it hangs under.
    """
    if kind not in set(Kind):
        raise HTTPException(404, "No level is served for that kind of node.")
    at = Ref(kind=Kind(kind), source=None, node_id=node_id)
    return spilled(viewer, session_id, at, thread, depth, opened, knobs)
