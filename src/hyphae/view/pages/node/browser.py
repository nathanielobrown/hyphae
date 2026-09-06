"""The one read every node page is: the session around the node, and the node read whole.

Five URLs and one answer. What differs per kind is a row of `kinds.KINDS` — its own header,
where it sits, what its children log lists, and what its pane previews — and everything else a
node page needs is read here: the session, the corpus the NavTree is built from, the enrichment
a pass wrote, and the page of children under the selection (`docs/viewer.md`).

The whole document from one open of the store, closed before anything renders (`view/deps.py`,
the window trade-off). Framework-free, so the three ways a node page is nothing are one
`Missing` — the route above turns it into the 404 it has always been.
"""

from dataclasses import replace
from math import ceil
from pathlib import Path

from hyphae.analyze.queries import ParamValue
from hyphae.model import MAIN_SOURCE
from hyphae.view import bounds, builders, failures, links, nodes
from hyphae.view.citation import Ran, cited
from hyphae.view.detail import enrichment_lines
from hyphae.view.enrichment import Descriptions, described
from hyphae.view.nodes import Kind, Ref
from hyphae.view.pages.node import models, nav_tree, reads, walk
from hyphae.view.pages.node.columns import COLUMNS
from hyphae.view.pages.node.kinds import EXPANDED, KINDS, Log, paged
from hyphae.view.pages.node.knobs import Knobs, pager, preset_choices
from hyphae.view.pages.node.levels import Levels
from hyphae.view.pages.node.markup.nav_tree import NavTreeRow
from hyphae.view.pages.node.models import Expansion, NodePage
from hyphae.view.store import Page, bound, open_store, page_rows


class Missing(Exception):
    """No node at that URL, in the words the kind that was asked for words it in."""


def browse(db: Path, session_id: str, at: Ref, knobs: Knobs, page: int) -> NodePage:
    """One node read whole: the NavTree with the path to the node open, and the pane's own reads.

    Every kind serves through here, because a node page is one response whatever the node is.
    What differs is `KINDS[at.kind]`, whose header cell answers `None` when the node is not in
    the store and whose `missing` is the 404 that becomes.

    The thread everything is read for is `at.source or MAIN_SOURCE`: `view_enrichment` keys
    turns by thread, and the NavTree spans the session, so a turn on another thread falls back
    to its prompt. The two session-wide nodes — a session and the unattached bucket — carry no
    thread of their own and are read on `main`.
    """
    spec = KINDS[at.kind]
    source = at.source or MAIN_SOURCE
    header_bound = bound(Page.SESSION_HEADER, bounds.HEADER_WIDTHS, session_id=session_id)
    # The session's runs are read once and printed twice: as a NavTree row at its width
    # and as a children log row at the log's. Cut to the wider of the two here, and cut
    # again at each — a row cut to the narrower would print a line already stopped.
    runs_bound = bound(Page.RUNS, bounds.LOG_WIDTHS, session_id=session_id)
    # Held from the first read rather than left to the corpus, so the two kinds whose header
    # *is* the session's read it back out of the memo instead of running it twice.
    levels = Levels()
    with open_store(db) as connection:
        head = levels.rows(connection, Page.SESSION_HEADER, **header_bound)
        if not head:
            raise Missing("No session with that id is in this store.")
        # The session's runs whole, once: a run is placed by the call that spawned it
        # rather than by the thread it ran on, so any level of the NavTree may need any of
        # them, and both buckets are defined against the same set.
        runs = page_rows(connection, Page.RUNS, **runs_bound)
        corpus = nav_tree.Corpus(
            session_id=session_id,
            # The rollup once per page: every row the NavTree draws reads its subtree total
            # out of this one climb over the runs.
            held=nodes.ledger(session_id, head[0]["cost_usd"] or 0, runs),
            runs=runs,
            described=described(connection, session_id, source),
            source=source,
            levels=levels,
        )
        found = spec.header(connection, corpus, at, paged(knobs.detail))
        if found is None:
            raise Missing(spec.missing)
        under = (
            spec.log(connection, corpus, at, page, knobs.log)
            if spec.log is not None
            else Log([], 0, [])
        )
        no_record: tuple[int | None, Ran] = (None, [])
        record, recorded = spec.record(connection, corpus, at) if spec.record else no_record
        built = nav_tree.nav_tree(
            connection,
            corpus,
            builders.session_node(head[0], corpus.held, corpus.described),
            nav_tree.ancestry(corpus, spec.trail(at, found.row)),
            knobs.nav,
            knobs.kin,
        )
        # What the reader reads before and after this node, off the same open path. Read
        # inside the request's own connection because it asks the store for levels the
        # NavTree did not open.
        walked = walk.neighbours(connection, corpus, built.chain)
        # The failures either side of this one, read only where the pane is standing on a
        # failure. A session-wide list is a query per page load and the step it answers
        # does not exist anywhere else, so every other node page asks the store nothing.
        failed = (
            failures.failures(connection, session_id)
            if built.chain[-1].kind is Kind.TOOL and built.chain[-1].is_error
            else None
        )
    # A page past the last of a level and a node that never had one are the same answer.
    # The first page is not: a node with no children still has its own facts to show.
    if page > 1 and not under.rows:
        raise Missing("This node's children do not run to that page.")
    selection = built.chain[-1]
    # Named from its own header rather than from the NavTree row it stands on (`KindSpec.titled`).
    # The words alone: what the node cost and what share of the session that is are the
    # NavTree's to work out, against the whole session rather than against one header.
    if spec.titled is not None:
        selection = replace(selection, words=spec.titled(corpus, at, found.row).words)
    ran: Ran = [
        (Page.SESSION_HEADER, header_bound),
        (Page.RUNS, runs_bound),
        *found.ran,
        *under.ran,
        *recorded,
        *built.ran,
        *walked.ran,
    ]
    # Only when the store held the tables to ask: a page cites what it ran, and over an
    # un-enriched store this query is not one of them.
    if corpus.described.queried:
        ran.append((Page.ENRICHMENT, {"session_id": session_id, "source": source}))
    # The same rule for the stepper's own read: a page cites what it ran, and most node
    # pages do not run this one.
    if failed is not None:
        ran.extend(failed.ran)
    about = spec.describe(corpus.described, at) if spec.describe is not None else None
    said = enrichment_lines(about, session_id, source)
    return NodePage(
        selection=selection,
        nav=models.Nav(
            choices=preset_choices(selection, knobs),
            rows=built.rows,
            # The thread the enrichment was read for: what a tail row's fetch carries.
            thread=source,
        ),
        body=models.Body(
            facts=reads.node_facts(selection, found.row),
            said=models.Said(about, said) if about and said else None,
            details=spec.details(corpus, at, found.row, knobs.detail) if spec.details else [],
            # The bytes behind the node: the thread's transcript, and — for a turn — the
            # one line it was read from.
            archived=models.Archived(
                thread_url=nodes.thread_url(session_id, source), line_no=record
            ),
        ),
        bearings=models.Bearings(
            # Where the chain starts: the whole session list, and this session's project.
            # The project is a step out of the session rather than a node of it, so it
            # stands above the chain rather than in it — a session is still the outermost
            # node.
            trail=models.Trail(
                list_url=links.LIST_URL,
                project_dir=head[0]["project_dir"],
                project_url=links.project_link(head[0]["project_filter"]),
            ),
            chain=built.chain,
            # Where the reading order goes from here, in both directions.
            walked=models.Steps(walked.previous, walked.next),
            # And where the session failed: how many failures it holds, which is what the
            # way into the list says, beside the step to the next one where there is one.
            tool_errors=head[0]["tool_errors"],
            failures=failures.stepped(failed.listed, selection) if failed else None,
        ),
        children=models.Children(
            shape=spec.under,
            rows=under.rows,
            # The level's own size, and where in it this page sits — the heading counts the
            # first, the control under the log reads the second.
            total=under.total,
            pager=pager(selection.url, knobs, page, ceil(under.total / knobs.log)),
        ),
        citations={named.value: cited(named, binding) for named, binding in ran},
        # What every href on the page carries, so a click serves the URL it displays.
        suffix=knobs.suffix,
    )


def opened(db: Path, session_id: str, at: Ref, log: int) -> Expansion:
    """One node's body alone, the way an expansion in someone else's log mounts it.

    The same header queries the pane reads through, so the two cannot drift apart. What it
    does not open is another level: a count and a link stand in for one, except where the
    level below opens nothing further (`docs/viewer.md`).
    """
    spec = KINDS[at.kind]
    # A kind no children log lists has no expansion — nothing offers one, and there is no row
    # of anybody's table for it to stand in (`nodes.Node.expansion`). It is the same four kinds
    # a header names, which is what lets this read `titled` without a second answer for None.
    if spec.listed_as is None or spec.titled is None:
        raise Missing("No expansion is served for that kind of node.")
    source = str(at.source)
    keyed: dict[str, ParamValue] = {"session_id": session_id, "source": source}
    with open_store(db) as connection:
        # An expansion prices nothing and lists no runs: every node it builds carries the empty
        # ledger, and what it wants of a corpus is the session it is in and the words a pass
        # wrote. Read for the thread in the URL — which for a run is the run's own id, the
        # source its rows carry — so the title is the one the log row that opened this had.
        corpus = nav_tree.Corpus(
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
            raise Missing(spec.missing)
        # The level the expansion lists, where its kind lists one: the first page of it, at the
        # size the reader is reading logs under. Which page is not a question an expansion
        # asks — the way past the first is the link to the node's own page.
        under = (
            spec.log(connection, corpus, at, 1, log)
            if spec.opens and spec.log is not None
            else Log([], 0, [])
        )
    ran: Ran = [*found.ran, *under.ran]
    if corpus.described.queried:
        ran.append((Page.ENRICHMENT, keyed))
    node = spec.titled(corpus, at, found.row)
    return Expansion(
        node=node,
        facts=reads.node_facts(node, found.row),
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


def spilled(
    db: Path, session_id: str, at: Ref, thread: str, depth: int, held: str, knobs: Knobs
) -> list[NavTreeRow]:
    """The children one level's window left out: the rows a `+N more` row stands in for.

    The NavTree draws a window on a level and a tail row saying how many it left out; this
    reads the rest of that level, at the depth the NavTree had reached, so a click can stand
    them where the tail row stood. `held` is the key of the child the open path descends
    through, which the window keeps wherever in the level it sits — the page sent it so
    that the two halves of one split agree, and this is the half that must not repeat it.

    `thread` is the reader's, not the level's: the enrichment is keyed by thread, so a page
    draws a turn of any other thread by its prompt, and a row read here has to come back
    the way the page beside it would have drawn it.

    Unbounded on purpose: what comes back is a level less a window, so a node with ten
    thousand children answers with ten thousand rows.
    """
    keyed: dict[str, ParamValue] = {"session_id": session_id}
    with open_store(db) as connection:
        head = page_rows(
            connection,
            Page.SESSION_HEADER,
            **bound(Page.SESSION_HEADER, bounds.HEADER_WIDTHS, session_id=session_id),
        )
        if not head:
            raise Missing("No session with that id is in this store.")
        # The NavTree's width, where the page read above takes the same query at the log's: what
        # comes back here is drawn as rows and listed in no children log, so the wider read
        # would fetch three times the string for a surface printing a third of it. Nothing
        # rendered says which was chosen — the row cuts to its own width whatever arrives —
        # so `tests/view/test_bounds__widths.py` is what holds it.
        runs = page_rows(connection, Page.RUNS, **bound(Page.RUNS, bounds.NAV_TREE_WIDTHS, **keyed))
        corpus = nav_tree.Corpus(
            session_id=session_id,
            held=nodes.ledger(session_id, head[0]["cost_usd"] or 0, runs),
            runs=runs,
            described=described(connection, session_id, thread),
            source=thread,
        )
        level = nav_tree.children(connection, corpus, at, knobs.nav, held or None)
    # Each row shut, and under it whatever a shut row stands: the runs it hides come back
    # with it, the way the page's own rows carry them. None of them is a step of the open
    # path — the cap keeps the child the path descends through inside the window, and this
    # read is what it left out.
    return [
        row
        for node in nav_tree.windowed(level.nodes, knobs.kin, [held]).cut
        for row in [
            NavTreeRow(node, depth, selected=False, ancestor=False),
            *nav_tree.spread(corpus, node, depth + 1),
        ]
    ]
