"""What the small fetches read: a popover's numbers, a fat value whole, one archived record.

A fragment reads through the connection its route holds open rather than a window of its own —
it is one row, and closing the store between the row and the markup would cost more than the
lock it gives back (`view/deps.py`). What it does not leave to the route is the query it ran,
the values it bound, or the row that came back: those stop here, and what crosses is typed.

The three ways a fragment is nothing are the browser's one `Missing`, which the route above
turns into the 404 it has always been. What a missing node says is the kind table's own
sentence, so a popover and the page for the same node refuse in the same words
(`pages/node/kinds.py`).
"""

from collections.abc import Mapping

import duckdb

from hyphae.analyze import queries
from hyphae.analyze.queries import ParamValue
from hyphae.view import bounds
from hyphae.view.detail import Spec, Written, syntax_of
from hyphae.view.enrichment import enriched
from hyphae.view.nodes import Kind, Ref
from hyphae.view.pages.node import reads
from hyphae.view.pages.node.browser import Missing
from hyphae.view.pages.node.kinds import KINDS
from hyphae.view.pages.node.models import Detailed, Measured, Popover, Record, Whole
from hyphae.view.pages.node.numbers import breakout, charges, spend, wash
from hyphae.view.store import Fragment, Row, Value, bound, page_rows


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
            raise Missing(KINDS[kind].missing)
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
    # for one that is — a node with no api calls under it is a real reading, and the popover
    # prints it as the dashes it is.
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
        # And the two lines under them, where agent runs hang below this node: None where
        # none does, which is what keeps the breakout off every other row.
        breakout=breakout(read.cost_usd, read.subtree_usd, whole),
    )


def compacted(
    connection: duckdb.DuckDBPyConnection, session_id: str, source: str, compaction_id: str
) -> Measured:
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
        raise Missing(KINDS[Kind.COMPACTION].missing)
    return Measured(
        key=Ref(Kind.COMPACTION, source, compaction_id).key,
        citation=queries.citation(Fragment.COMPACTION_NUMBERS, keyed),
        node=reads.compaction_numbers(rows[0]),
    )


def detailed(
    connection: duckdb.DuckDBPyConnection, spec: Spec, keys: Mapping[str, str]
) -> Detailed:
    """One Detail whole, and the syntax it is marked up as.

    `keys` are the path's own, which the spec's route template minted and `queries.citation`
    prints back into the line the fragment carries. A key the query does not bind is a crash
    here, which is a route registered against the wrong `whole`.

    Nothing asks the row what it is holding except through `syntax_of`, so a pane and its
    fetch cannot mark the same value up two ways.
    """
    if spec.written is Written.LINE and not enriched(connection):
        # A pass creates the enrichment tables rather than the exporter, so a store none has
        # touched holds no such line — the same nothing a missing row is, and the same answer
        # (`view/enrichment.py`). Asked per request and not at startup, because a pass can run
        # against the store while the viewer is reading it. Ahead of the read, which would
        # otherwise fail on the missing table rather than on the missing line.
        raise Missing("No enrichment pass has written to this store.")
    # The statement decides which of the sixteen takes a width, not the `Written` arm: only
    # the named-file read declares `head_chars`, and it is not a cut of the answer — which
    # rides whole — but the bound on the file suffix beside it, which says how the answer is
    # marked up. A fetch prints at the pane's widths, so it names the pane's surface.
    keyed = bound(spec.whole, bounds.HEADER_WIDTHS, **keys)
    row = _one(connection, spec.whole, keyed, "value")
    return Detailed(
        whole=Whole(row["value"], spec.name, queries.citation(spec.whole, keyed)),
        syntax=syntax_of(spec.written, row),
    )


def recorded(
    connection: duckdb.DuckDBPyConnection, session_id: str, source: str, line_no: int
) -> Record:
    """One archived record whole, as the browser's preview was cut from."""
    keyed = {"session_id": session_id, "source": source, "line_no": line_no}
    # The record itself, which the store holds NOT NULL.
    row = _one(connection, Value.RECORD, keyed, "raw")
    return reads.record_value(row, queries.citation(Value.RECORD, keyed))


def _one(
    connection: duckdb.DuckDBPyConnection,
    value: Value,
    keyed: Mapping[str, ParamValue],
    column: str,
) -> Row:
    """The one row a per-value fragment is for.

    `column` is where the query puts the value this fragment is for. A row can exist with
    nothing under it — a `Read` has no command, a turn no prompt — and that is a 404 and not
    an empty page: nothing on a pane links here unless there is a value to fetch, so a request
    for one that is not there is a URL somebody typed or a link somebody kept.
    """
    rows = page_rows(connection, value, **keyed)
    if not rows or rows[0][column] is None:
        raise Missing("Nothing in this store is stored under that id.")
    return rows[0]
