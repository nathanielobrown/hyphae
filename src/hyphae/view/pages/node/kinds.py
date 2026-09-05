"""One row per kind of node: what its page reads, lists and previews, and what lists it.

The eight kinds a session holds differ in what a pane reads for them and in little else — the
NavTree beside it, the crumbs above it, the walk under it and the citations below are the same
page whatever the page is about. `KINDS` is where that difference is spelled, one row per kind
and total over `Kind`, read by the node page (`routes/browse.py`) and by the expansion a log
row opens (`routes/expansions.py`) alike. What hangs *under* a kind in the NavTree is the other
table, `nav_tree.LEVELS`.

Framework-free on purpose: a header cell answers `None` where the store holds no such node, and
the route beside it turns that into the 404 the row's `missing` spells. Every cell takes the
`Ref` and derives its ids from it, so a caller holding a ref needs nothing else from the URL.
"""

from collections.abc import Callable, Mapping
from typing import NamedTuple

import duckdb

from hyphae.analyze.queries import ParamValue
from hyphae.model import MAIN_SOURCE
from hyphae.view import bounds, builders, detail, nodes
from hyphae.view.citation import Ran
from hyphae.view.detail import Detail, details, preview
from hyphae.view.enrichment import Descriptions, Enrichment
from hyphae.view.nodes import Kind, Node, Ref
from hyphae.view.pages.node import nav_tree, reads
from hyphae.view.pages.node.columns import Shape
from hyphae.view.pages.node.knobs import skipped, sliced
from hyphae.view.pages.node.markup.logs import Logged
from hyphae.view.store import (
    NO_SIZES,
    TURN_CURSOR,
    Fragment,
    Page,
    Row,
    bound,
    listed,
    page_rows,
    window,
)


class Read(NamedTuple):
    """The surface a header is read at: its widths, and the sizes the reader asked for.

    Two exist. A page reads at `bounds.HEADER_WIDTHS` and passes `?detail=` as a size; an
    expansion reads at `bounds.EXPANSION_WIDTHS`, which declares its own detail width and takes
    no size. A header whose query has no `detail_chars` to fill ignores the sizes — `store.bound`
    raises on one the query does not declare.
    """

    widths: bounds.Widths
    sizes: Mapping[str, ParamValue]


EXPANDED = Read(bounds.EXPANSION_WIDTHS, NO_SIZES)


def paged(size: int) -> Read:
    """The surface a node page reads its header at, cut to the `?detail=` it was asked for."""
    return Read(bounds.HEADER_WIDTHS, {"detail_chars": size})


class Found(NamedTuple):
    """One node's own header row, beside the query line that produced it."""

    row: Row
    ran: Ran


class Log(NamedTuple):
    """One page of a children log: the rows, the size of the level, and what was run.

    `total` counts the level rather than the page — the heading says how many children there
    are and the pager divides that by the size the reader asked for.
    """

    rows: list[Logged]
    total: int
    ran: Ran


Header = Callable[[duckdb.DuckDBPyConnection, nav_tree.Corpus, Ref, Read], Found | None]
Trail = Callable[[Ref, Row], list[Ref]]
Logs = Callable[[duckdb.DuckDBPyConnection, nav_tree.Corpus, Ref, int, int], Log]
Details = Callable[[nav_tree.Corpus, Ref, Row, int], list[Detail]]
Record = Callable[[duckdb.DuckDBPyConnection, nav_tree.Corpus, Ref], tuple[int | None, Ran]]
Titled = Callable[[nav_tree.Corpus, Ref, Row], Node]
Describe = Callable[[Descriptions, Ref], Enrichment | None]


class KindSpec(NamedTuple):
    """What one kind of node is to the two surfaces that read it: a page, and an expansion.

    A cell is `None` where the kind has nothing of that sort: a compaction previews no fat
    value, a tool call logs no children, and five of the eight are described by no pass.
    """

    # The node's own row, or None where the store holds no such node — which the route answers
    # with `missing`, the 404 text this kind spells.
    header: Header
    missing: str
    # Whether the node reads at a `/thread/{source}/…` URL. The four that do share one route
    # and one body mount; the rest each have a path of their own, and answering for one here
    # would key its header by a thread it was never recorded on.
    in_thread: bool
    # What `nav_tree.ancestry` is seeded with, innermost last: a call and a tool name their turn
    # in their own header, so neither costs a read to place.
    trail: Trail
    # The shape of children log under the node, and the header column counting the level for an
    # expansion, which counts what it does not list.
    under: Shape
    counts: str | None
    # Whether an expansion lists that level instead of only counting it — true for the api call
    # alone, whose tool calls open nothing further, so the level a reader opens is still the last.
    opens: bool
    log: Logs | None
    details: Details | None
    record: Record | None
    # The pane's own node, named from its own header rather than from the NavTree row it stands
    # on: a NavTree row is cut to a third of what a title has to spend (`nodes.Node.pane_title`).
    # None where no cut reaches the name — a session is read from its own header already, a
    # compaction is named by its trigger, and a bucket is named by the viewer.
    titled: Titled | None
    describe: Describe | None
    # The shape of log this kind is listed *in*, which is what an expansion's row spans.
    listed_as: Shape | None


def _keys(corpus: nav_tree.Corpus, at: Ref, binds: str, threaded: bool) -> dict[str, str]:
    """What a read of one node binds: the session, the thread where the query takes one, and
    the node's own id under the name that query calls it."""
    keys = {"session_id": corpus.session_id}
    if threaded:
        keys["source"] = str(at.source)
    return keys | {binds: at.node_id}


def keyed(page: Page, binds: str, *, threaded: bool = True) -> Header:
    """The header cell of a kind the store answers for by id — five of the eight.

    `binds` is what the header query calls that id. `threaded` is false for the agent run
    alone: a run's own rows carry its id as their thread, so one key answers both questions
    and the query takes no source.
    """

    def read(
        connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, reading: Read
    ) -> Found | None:
        bindings = bound(page, reading.widths, reading.sizes, **_keys(corpus, at, binds, threaded))
        rows = page_rows(connection, page, **bindings)
        return Found(rows[0], [(page, bindings)]) if rows else None

    return read


def _session_header(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, reading: Read
) -> Found | None:
    """The session's own header, which the page around this has read already.

    Read back through the request's `Levels` rather than passed in: the page needs the row
    before any cell runs, to price the ledger every NavTree row draws a share of, so this is a
    memo hit and never a second statement (`levels.py`). Its sizes are ignored because the
    query declares no detail to cut.
    """
    bindings = bound(Page.SESSION_HEADER, reading.widths, session_id=corpus.session_id)
    rows = corpus.levels.rows(connection, Page.SESSION_HEADER, **bindings)
    return Found(rows[0], [(Page.SESSION_HEADER, bindings)]) if rows else None


def _loose(corpus: nav_tree.Corpus) -> list[Row]:
    """The session's agent runs no tool call spawned, out of the runs it already holds."""
    return [run for run in corpus.runs if run["spawn_source"] is None]


def _unattached_header(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, reading: Read
) -> Found | None:
    """The session's own header, where the session holds a run nothing placed.

    The bucket stands for no store row, so what it reads is the session it hangs off; what
    decides whether it exists at all is the runs, which every level of the NavTree needs anyway.
    """
    return _session_header(connection, corpus, at, reading) if _loose(corpus) else None


def _unattributed_header(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, reading: Read
) -> Found | None:
    """One thread's calls that answer no turn, as its timeline's own cursorless row reads them."""
    standing = nav_tree.unattributed(connection, corpus, str(at.source))
    return Found(standing.row, [standing.ran]) if standing else None


def _compaction_header(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, reading: Read
) -> Found | None:
    """One compaction, out of its thread's markers rather than by id.

    A compaction has no header query of its own: the thread's whole set is what the NavTree
    beside it renders anyway, so the read is shared and the pick is a filter in Python.
    """
    bindings = bound(
        Page.COMPACTIONS, reading.widths, session_id=corpus.session_id, source=str(at.source)
    )
    found = [
        row
        for row in page_rows(connection, Page.COMPACTIONS, **bindings)
        if row["compaction_id"] == at.node_id
    ]
    return Found(found[0], [(Page.COMPACTIONS, bindings)]) if found else None


def _own(at: Ref, row: Row) -> list[Ref]:
    """A node that names its own place: nothing above it a header had to answer for."""
    return [at]


def _call_trail(at: Ref, row: Row) -> list[Ref]:
    """The call's own header says which turn it answers, so its place costs no read: a NULL
    turn puts it in its thread's unattributed bucket instead."""
    return [nav_tree.home(str(at.source), row["turn_id"]), at]


def _tool_trail(at: Ref, row: Row) -> list[Ref]:
    """The whole path down out of one read: the call that made it, and the turn that call
    answers — else that thread's bucket, by the same rule."""
    return [
        nav_tree.home(str(at.source), row["turn_id"]),
        Ref(Kind.CALL, at.source, row["api_call_id"]),
        at,
    ]


def _compaction_trail(at: Ref, row: Row) -> list[Ref]:
    """Under the turn it happened during, else beside the turns of its thread. Seeded rather
    than resolved, because a turn a timestamp lands in is a read this row has made."""
    turn_id = row["turn_id"]
    return [*([Ref(Kind.TURN, at.source, turn_id)] if turn_id is not None else []), at]


def _turn_rows(corpus: nav_tree.Corpus, source: str, rows: list[Row]) -> list[Logged]:
    """A page of one thread's timeline as a children log reads it: a row per turn."""
    return [
        reads.logged(
            Shape.TURNS,
            builders.turn_node(
                corpus.session_id,
                source,
                row,
                corpus.held,
                corpus.turn_text(source, row["turn_id"]),
            ),
            row,
        )
        for row in rows
    ]


def _timeline_log(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, page: int, size: int
) -> Log:
    """The main thread's turns, which is what a session's own children log lists."""
    offset = skipped(page, size)
    binds = bound(Page.TIMELINE, bounds.LOG_WIDTHS, session_id=corpus.session_id)
    turns = window(connection, Page.TIMELINE, TURN_CURSOR, offset, size, **binds)
    return Log(
        _turn_rows(corpus, MAIN_SOURCE, turns.rows),
        turns.total,
        [(Page.TIMELINE, binds | {"offset": offset, "limit": size})],
    )


def _run_timeline_log(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, page: int, size: int
) -> Log:
    """An agent run's own thread of turns, keyed by the run id its rows carry as their source."""
    offset = skipped(page, size)
    binds = bound(
        Page.RUN_TIMELINE, bounds.LOG_WIDTHS, session_id=corpus.session_id, source=at.node_id
    )
    turns = window(connection, Page.RUN_TIMELINE, TURN_CURSOR, offset, size, **binds)
    return Log(
        _turn_rows(corpus, at.node_id, turns.rows),
        turns.total,
        [(Page.RUN_TIMELINE, binds | {"offset": offset, "limit": size})],
    )


def _calls_log(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, page: int, size: int
) -> Log:
    """The api calls under a turn — or, at `turn_id` NULL, under a thread's bucket.

    One cell for both because the two differ by that binding alone, which is the same rule the
    NavTree's level reads by: a call answering no turn sits in its thread's bucket.
    """
    source = str(at.source)
    binds = bound(
        Fragment.TURN_CALLS,
        bounds.LOG_WIDTHS,
        session_id=corpus.session_id,
        source=source,
        turn_id=None if at.kind is Kind.UNATTRIBUTED else at.node_id,
        skipped=skipped(page, size),
        page_calls=size,
    )
    calls = listed(page_rows(connection, Fragment.TURN_CALLS, **binds))
    return Log(
        [
            reads.logged(
                Shape.CALLS, builders.call_node(corpus.session_id, source, row, corpus.held), row
            )
            for row in calls.rows
        ],
        calls.total,
        [(Fragment.TURN_CALLS, binds)],
    )


def _tools_log(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, page: int, size: int
) -> Log:
    """The tool calls one api call made.

    Priced at nothing on purpose: what a tool call cost is the call's, and a row here that
    carried the ledger would draw a badge for money it did not spend.
    """
    source = str(at.source)
    binds = bound(
        Fragment.CALL_TOOLS,
        bounds.LOG_WIDTHS,
        session_id=corpus.session_id,
        source=source,
        api_call_id=at.node_id,
        skipped=skipped(page, size),
        page_tools=size,
    )
    called = listed(page_rows(connection, Fragment.CALL_TOOLS, **binds))
    return Log(
        [
            reads.logged(
                Shape.TOOLS,
                builders.tool_node(corpus.session_id, source, row, nodes.NO_LEDGER),
                row,
            )
            for row in called.rows
        ],
        called.total,
        [(Fragment.CALL_TOOLS, binds)],
    )


def _unattached_log(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref, page: int, size: int
) -> Log:
    """The runs nothing placed, paged out of the set the corpus already holds — so this is a
    slice rather than a read, and the level cites nothing of its own."""
    runs = sliced(_loose(corpus), page, size)
    return Log(
        [
            reads.logged(
                Shape.RUNS,
                builders.run_node(
                    corpus.session_id, row, corpus.held, corpus.run_text(row["run_id"])
                ),
                row,
            )
            for row in runs.rows
        ],
        runs.total,
        [],
    )


def _turn_details(corpus: nav_tree.Corpus, at: Ref, row: Row, size: int) -> list[Detail]:
    """What the turn was asked, and the arguments where a slash command was what asked it."""
    keys = _keys(corpus, at, "turn_id", True)
    return details(
        preview(detail.TURN_PROMPT, row, size=size, **keys),
        preview(detail.TURN_COMMAND_ARGS, row, size=size, **keys),
    )


def _run_details(corpus: nav_tree.Corpus, at: Ref, row: Row, size: int) -> list[Detail]:
    """The brief the run was given, then the ask and the answer off the call that spawned it."""
    keys = _keys(corpus, at, "run_id", False)
    return details(
        preview(detail.RUN_BRIEF, row, size=size, **keys),
        preview(detail.RUN_PROMPT, row, size=size, **keys),
        preview(detail.RUN_RESULT, row, size=size, **keys),
    )


def _call_details(corpus: nav_tree.Corpus, at: Ref, row: Row, size: int) -> list[Detail]:
    """What the model said, and what it thought before saying it."""
    keys = _keys(corpus, at, "api_call_id", True)
    return details(
        preview(detail.CALL_TEXT, row, size=size, **keys),
        preview(detail.CALL_THINKING, row, size=size, **keys),
    )


def _tool_details(corpus: nav_tree.Corpus, at: Ref, row: Row, size: int) -> list[Detail]:
    """The command first, where the call ran one: it is what the input is about, and the input
    below it is the record it was read out of."""
    keys = _keys(corpus, at, "tool_call_id", True)
    return details(
        preview(detail.TOOL_COMMAND, row, size=size, **keys),
        preview(detail.TOOL_INPUT, row, size=size, **keys),
        preview(detail.TOOL_RESULT, row, size=size, **keys),
    )


def _turn_record(
    connection: duckdb.DuckDBPyConnection, corpus: nav_tree.Corpus, at: Ref
) -> tuple[int | None, Ran]:
    """Which line of the transcript the turn was read from.

    Read for the whole thread because that is what the query answers; two identifier columns
    per turn, and the pane keeps the one row it is about. Only a turn has one: `turns.id` is a
    record's `uuid`, which is the store's own join down to the bytes Claude Code wrote.
    """
    thread: dict[str, ParamValue] = {"session_id": corpus.session_id, "source": str(at.source)}
    archived = {
        row["turn_id"]: row["line_no"] for row in page_rows(connection, Page.TURN_RECORDS, **thread)
    }
    return archived.get(at.node_id), [(Page.TURN_RECORDS, thread)]


def _turn_titled(corpus: nav_tree.Corpus, at: Ref, row: Row) -> Node:
    return builders.turn_node(
        corpus.session_id,
        str(at.source),
        row,
        corpus.held,
        corpus.turn_text(str(at.source), row["turn_id"]),
    )


def _run_titled(corpus: nav_tree.Corpus, at: Ref, row: Row) -> Node:
    return builders.run_node(corpus.session_id, row, corpus.held, corpus.run_text(row["run_id"]))


def _call_titled(corpus: nav_tree.Corpus, at: Ref, row: Row) -> Node:
    return builders.call_node(corpus.session_id, str(at.source), row, corpus.held)


def _tool_titled(corpus: nav_tree.Corpus, at: Ref, row: Row) -> Node:
    return builders.tool_node(corpus.session_id, str(at.source), row, corpus.held)


# Three kinds a pass describes, and the map it wrote each into. Turns are keyed by thread —
# which is the thread the page was read for, so the selection is always in reach of its own.
KINDS: dict[Kind, KindSpec] = {
    Kind.SESSION: KindSpec(
        header=_session_header,
        missing="No session with that id is in this store.",
        in_thread=False,
        trail=_own,
        under=Shape.TURNS,
        counts=None,
        opens=False,
        log=_timeline_log,
        details=None,
        record=None,
        titled=None,
        describe=lambda descriptions, at: descriptions.session,
        listed_as=None,
    ),
    Kind.TURN: KindSpec(
        header=keyed(Page.TURN_HEADER, "turn_id"),
        missing="No turn with that id is in this thread.",
        in_thread=True,
        trail=_own,
        under=Shape.CALLS,
        counts="api_calls",
        opens=False,
        log=_calls_log,
        details=_turn_details,
        record=_turn_record,
        titled=_turn_titled,
        describe=lambda descriptions, at: descriptions.turns.get(at.node_id),
        listed_as=Shape.TURNS,
    ),
    Kind.RUN: KindSpec(
        header=keyed(Page.RUN_HEADER, "run_id", threaded=False),
        missing="No agent run with that id is in this session.",
        in_thread=False,
        trail=_own,
        under=Shape.TURNS,
        counts="turns",
        opens=False,
        log=_run_timeline_log,
        details=_run_details,
        record=None,
        titled=_run_titled,
        describe=lambda descriptions, at: descriptions.runs.get(at.node_id),
        listed_as=Shape.RUNS,
    ),
    Kind.CALL: KindSpec(
        header=keyed(Page.CALL_HEADER, "api_call_id"),
        missing="No api call with that id is in this thread.",
        in_thread=True,
        trail=_call_trail,
        under=Shape.TOOLS,
        counts="tool_calls",
        opens=True,
        log=_tools_log,
        details=_call_details,
        record=None,
        titled=_call_titled,
        describe=None,
        listed_as=Shape.CALLS,
    ),
    Kind.TOOL: KindSpec(
        header=keyed(Page.TOOL_HEADER, "tool_call_id"),
        missing="No tool call with that id is in this thread.",
        in_thread=True,
        trail=_tool_trail,
        under=Shape.NONE,
        counts=None,
        opens=False,
        log=None,
        details=_tool_details,
        record=None,
        titled=_tool_titled,
        describe=None,
        listed_as=Shape.TOOLS,
    ),
    Kind.COMPACTION: KindSpec(
        header=_compaction_header,
        missing="No compaction with that id is in this thread.",
        in_thread=True,
        trail=_compaction_trail,
        under=Shape.NONE,
        counts=None,
        opens=False,
        log=None,
        details=None,
        record=None,
        titled=None,
        describe=None,
        listed_as=None,
    ),
    Kind.UNATTRIBUTED: KindSpec(
        header=_unattributed_header,
        missing="Every api call on this thread answers a turn.",
        in_thread=False,
        trail=_own,
        under=Shape.CALLS,
        counts=None,
        opens=False,
        log=_calls_log,
        details=None,
        record=None,
        titled=None,
        describe=None,
        listed_as=None,
    ),
    Kind.UNATTACHED: KindSpec(
        header=_unattached_header,
        missing="Every agent run in this session was placed.",
        in_thread=False,
        trail=_own,
        under=Shape.RUNS,
        counts=None,
        opens=False,
        log=_unattached_log,
        details=None,
        record=None,
        titled=None,
        describe=None,
        listed_as=None,
    ),
}
