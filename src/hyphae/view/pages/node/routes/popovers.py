"""The numbers behind one NavTree row, fetched when a reader points at it or tabs to it.

One popover per node, and one route per kind because each kind is keyed differently. What it
draws is what the row already shows — the cost badge and the context bar — written out: the
node's own spend, and what the agent runs under it spent broken out below (`CONTEXT.md`).

A popover is one row, so it reads through `Db` rather than a window of its own: the read is
too small to be worth closing the store between the row and the markup (`view/deps.py`).
"""

from collections.abc import Callable
from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from hyphae.model import MAIN_SOURCE
from hyphae.view import nodes
from hyphae.view.components import Html
from hyphae.view.deps import Db, ViewerDep
from hyphae.view.nodes import Kind
from hyphae.view.pages.node import fragments
from hyphae.view.pages.node.browser import Missing
from hyphae.view.pages.node.markup import numbers
from hyphae.view.pages.node.models import Measured, Popover

router = APIRouter()


def refused(read: Callable[[], Popover | Measured]) -> Popover | Measured:
    """A node the store does not hold, as the 404 it has always been."""
    try:
        return read()
    except Missing as gone:
        raise HTTPException(404, str(gone)) from gone


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
    """One compaction's numbers, read on the thread its row carries."""
    return refused(lambda: fragments.compacted(connection, session_id, source, compaction_id))


def node_read(
    kind: str, session_id: str, source: str, node_id: str, connection: Db
) -> Popover | Measured:
    """The numbers behind a turn, an api call, or a tool call recorded on a thread."""
    if kind not in nodes.NUMBERED:
        raise HTTPException(404, "No numbers are served for that kind of node.")
    return refused(lambda: fragments.counted(connection, Kind(kind), session_id, source, node_id))


def run_read(session_id: str, run_id: str, connection: Db) -> Popover | Measured:
    """One agent run's numbers, read on the thread the run's id also names."""
    return refused(lambda: fragments.counted(connection, Kind.RUN, session_id, run_id, run_id))


def session_read(session_id: str, connection: Db) -> Popover | Measured:
    """A whole session's numbers: the main thread's window, and every thread's spend."""
    return refused(
        lambda: fragments.counted(connection, Kind.SESSION, session_id, MAIN_SOURCE, session_id)
    )


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
