"""The numbers behind one NavTree row, fetched when a reader points at it or tabs to it.

One popover per node, and one route per kind because each kind is keyed differently. What it
draws is what the row already shows — the cost badge and the context bar — written out: the
node's own spend, and what the agent runs under it spent broken out below (`CONTEXT.md`).

A popover is one row, so it reads through `Db` rather than a window of its own: the read is
too small to be worth closing the store between the row and the markup (`view/deps.py`).
"""

from typing import Annotated, assert_never

import duckdb
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from hyphae.analyze import queries
from hyphae.model import MAIN_SOURCE
from hyphae.view import bounds, nodes
from hyphae.view.components import Html
from hyphae.view.deps import Db, ViewerDep
from hyphae.view.nodes import Kind, Ref
from hyphae.view.pages.node import reads
from hyphae.view.pages.node.markup import numbers
from hyphae.view.pages.node.models import Measured, Popover
from hyphae.view.pages.node.numbers import breakout, charges, spend, wash
from hyphae.view.store import Fragment, bound, page_rows

router = APIRouter()


def counted(
    connection: duckdb.DuckDBPyConnection, kind: Kind, session_id: str, source: str, node_id: str
) -> Popover | Measured:
    """One node's numbers, for the popover its NavTree row fetches.

    `source` is the thread the window is read on, which is not always the thread the node
    sits on: a session's reader is reading `main`, and its spend is every thread's. What
    differs between the kinds is inside the query; what differs here is only the tool call,
    which has no api calls to be measured out of.
    """
    if kind is Kind.TOOL:
        keyed = bound(
            Fragment.TOOL_NUMBERS,
            bounds.POPOVER_WIDTHS,
            session_id=session_id,
            source=source,
            tool_call_id=node_id,
        )
        rows = page_rows(connection, Fragment.TOOL_NUMBERS, **keyed)
        if not rows:
            raise HTTPException(404, "No tool call with that id is in this thread.")
        return Measured(
            key=Ref(kind, source, node_id).key,
            citation=queries.citation(Fragment.TOOL_NUMBERS, keyed),
            node=reads.tool_numbers(rows[0]),
        )
    binds = bound(
        Fragment.NUMBERS,
        bounds.POPOVER_WIDTHS,
        session_id=session_id,
        source=source,
        node_id=node_id,
        kind=kind,
    )
    rows = page_rows(connection, Fragment.NUMBERS, **binds)
    # The query aggregates, so it answers a row for a node that is not there as readily as
    # for one that is — a node with no api calls under it is a real reading, and the
    # popover prints it as the dashes it is.
    read = reads.node_numbers(rows[0])
    whole = read.session_usd
    return Popover(
        key=Ref(kind, source, node_id).key,
        citation=queries.citation(Fragment.NUMBERS, binds),
        window=read.window,
        # The three lines between the window and the total, each priced and washed here
        # rather than in the component: what a charge is made of is arithmetic
        # (`view/numbers.py`), and the total under them takes the same ground.
        charges=charges(read, spend(read.spent), whole),
        total_wash=wash(read.cost_usd, whole),
        # And the two lines under them, where agent runs hang below this node.
        breakout=breakout(read.cost_usd, read.subtree_usd, whole),
    )


def drawn(read: Popover | Measured) -> Html:
    """One reading in the component its own type names."""
    if isinstance(read, Popover):
        return numbers.popover(
            key=read.key,
            citation=read.citation,
            node=read.window,
            charges=read.charges,
            total_wash=read.total_wash,
            breakout=read.breakout,
        )
    match read.node:
        case numbers.Tool() as tool:
            return numbers.tool(key=read.key, citation=read.citation, node=tool)
        case numbers.Compaction() as compacted:
            return numbers.compaction(key=read.key, citation=read.citation, node=compacted)
        case _:
            assert_never(read.node)


def compaction_read(
    session_id: str, source: str, compaction_id: str, connection: Db
) -> Popover | Measured:
    """One compaction's numbers: the window it dropped, and the word recorded for why.

    Its own read rather than a branch of `counted`, because a compaction shares nothing with
    the kinds made of api calls — no window to stand on, no model, no dollar.
    """
    keyed = bound(
        Fragment.COMPACTION_NUMBERS,
        bounds.POPOVER_WIDTHS,
        session_id=session_id,
        source=source,
        compaction_id=compaction_id,
    )
    rows = page_rows(connection, Fragment.COMPACTION_NUMBERS, **keyed)
    if not rows:
        raise HTTPException(404, "No compaction with that id is on this thread.")
    return Measured(
        key=Ref(Kind.COMPACTION, source, compaction_id).key,
        citation=queries.citation(Fragment.COMPACTION_NUMBERS, keyed),
        node=reads.compaction_numbers(rows[0]),
    )


def node_read(
    kind: str, session_id: str, source: str, node_id: str, connection: Db
) -> Popover | Measured:
    """The numbers behind a turn, an api call, or a tool call recorded on a thread."""
    if kind not in nodes.NUMBERED:
        raise HTTPException(404, "No numbers are served for that kind of node.")
    return counted(connection, Kind(kind), session_id, source, node_id)


def run_read(session_id: str, run_id: str, connection: Db) -> Popover | Measured:
    """One agent run's numbers, read on the thread the run's id also names."""
    return counted(connection, Kind.RUN, session_id, run_id, run_id)


def session_read(session_id: str, connection: Db) -> Popover | Measured:
    """A whole session's numbers: the main thread's window, and every thread's spend."""
    return counted(connection, Kind.SESSION, session_id, MAIN_SOURCE, session_id)


def compaction_markup(read: Annotated[Popover | Measured, Depends(compaction_read)]) -> Html:
    return drawn(read)


def node_markup(read: Annotated[Popover | Measured, Depends(node_read)]) -> Html:
    return drawn(read)


def run_markup(read: Annotated[Popover | Measured, Depends(run_read)]) -> Html:
    return drawn(read)


def session_markup(read: Annotated[Popover | Measured, Depends(session_read)]) -> Html:
    return drawn(read)


CompactionNumbers = Annotated[Html, Depends(compaction_markup)]
NodeNumbers = Annotated[Html, Depends(node_markup)]
RunNumbers = Annotated[Html, Depends(run_markup)]
SessionNumbers = Annotated[Html, Depends(session_markup)]


@router.get(
    f"{nodes.NUMBERS_URL}/session/{{session_id}}/thread/{{source}}"
    f"/{Kind.COMPACTION}/{{compaction_id}}"
)
def compaction_numbers(popover: CompactionNumbers, viewer: ViewerDep) -> Response:
    """One compaction's numbers.

    It must stay above the route below it, whose `{kind}` matches this path too: which of the
    two answers is decided by the order they are registered in.
    """
    return viewer.html(popover)


@router.get(f"{nodes.NUMBERS_URL}/session/{{session_id}}/thread/{{source}}/{{kind}}/{{node_id}}")
def node_numbers(popover: NodeNumbers, viewer: ViewerDep) -> Response:
    """The numbers behind a turn, an api call, or a tool call recorded on a thread."""
    return viewer.html(popover)


@router.get(f"{nodes.NUMBERS_URL}/session/{{session_id}}/{Kind.RUN}/{{run_id}}")
def run_numbers(popover: RunNumbers, viewer: ViewerDep) -> Response:
    """One agent run's numbers, read on the thread the run's id also names."""
    return viewer.html(popover)


@router.get(f"{nodes.NUMBERS_URL}/session/{{session_id}}")
def session_numbers(popover: SessionNumbers, viewer: ViewerDep) -> Response:
    """A whole session's numbers: the main thread's window, and every thread's spend."""
    return viewer.html(popover)
