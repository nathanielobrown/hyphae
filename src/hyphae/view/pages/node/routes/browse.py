"""The one response every node page is: the NavTree with a path open, beside the pane reading it.

Five URLs and one answer. What differs per kind is a row of `kinds.KINDS` — its own header,
where it sits, what its children log lists, and what its pane previews — and everything else a
node page needs is read here: the session, the corpus the NavTree is built from, the enrichment
a pass wrote, and the page of children under the selection (`docs/viewer.md`).
"""

from dataclasses import replace
from math import ceil

from fastapi import HTTPException
from fastapi.responses import Response

from hyphae.model import MAIN_SOURCE
from hyphae.view import bounds, builders, failures, links, nodes
from hyphae.view.citation import Ran, cited
from hyphae.view.deps import Viewer
from hyphae.view.detail import enrichment_lines
from hyphae.view.enrichment import described
from hyphae.view.nodes import Kind, Ref
from hyphae.view.pages.node import nav_tree, reads, walk
from hyphae.view.pages.node.kinds import KINDS, Log, paged
from hyphae.view.pages.node.knobs import Knobs, pager, preset_choices
from hyphae.view.pages.node.levels import Levels
from hyphae.view.pages.node.markup import page as node_page
from hyphae.view.store import Page, bound, open_store, page_rows


def browse(viewer: Viewer, session_id: str, at: Ref, knobs: Knobs, page: int) -> Response:
    """One node page: the NavTree with the path to the node open, beside the pane reading it.

    Every kind serves through here, because a node page is one response whatever the node is.
    What differs is `KINDS[at.kind]`, whose header cell answers `None` when the node is not in
    the store and whose `missing` is the 404 that becomes.

    The thread everything is read for is `at.source or MAIN_SOURCE`: `view_enrichment` keys
    turns by thread, and the NavTree spans the session, so a turn on another thread falls back
    to its prompt. The two session-wide nodes — a session and the unattached bucket — carry no
    thread of their own and are read on `main`.
    """
    # A page number below the first is a bad ask like a size outside its bounds, and is
    # answered the same way: no level has such a page, so what is wrong is the number and
    # not the node the URL names. Asked before anything is read — it would otherwise bind
    # a negative offset. A number past a level's *last* page is a 404 further down: that
    # one is a question about the node, and only the level can answer it.
    if page < 1:
        raise HTTPException(400, "Ask for a children log page from one upwards.")
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
    with open_store(viewer.db) as connection:
        head = levels.rows(connection, Page.SESSION_HEADER, **header_bound)
        if not head:
            raise HTTPException(404, "No session with that id is in this store.")
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
            raise HTTPException(404, spec.missing)
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
        raise HTTPException(404, "This node's children do not run to that page.")
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
    return viewer.html(
        node_page.page(
            selection=selection,
            nav=node_page.Nav(
                choices=preset_choices(selection, knobs),
                rows=built.rows,
                # The thread the enrichment was read for: what a tail row's fetch carries.
                thread=source,
            ),
            body=node_page.Body(
                facts=reads.node_facts(selection, found.row),
                said=node_page.Said(about, said) if about and said else None,
                details=spec.details(corpus, at, found.row, knobs.detail) if spec.details else [],
                # The bytes behind the node: the thread's transcript, and — for a turn — the
                # one line it was read from.
                archived=node_page.Archived(
                    thread_url=nodes.thread_url(session_id, source), line_no=record
                ),
            ),
            bearings=node_page.Bearings(
                # Where the chain starts: the whole session list, and this session's project.
                # The project is a step out of the session rather than a node of it, so it
                # stands above the chain rather than in it — a session is still the outermost
                # node.
                trail=node_page.Trail(
                    list_url=links.LIST_URL,
                    project_dir=head[0]["project_dir"],
                    project_url=links.project_link(head[0]["project_filter"]),
                ),
                chain=built.chain,
                # Where the reading order goes from here, in both directions.
                walked=node_page.Steps(walked.previous, walked.next),
                # And where the session failed: how many failures it holds, which is what the
                # way into the list says, beside the step to the next one where there is one.
                tool_errors=head[0]["tool_errors"],
                failures=failures.stepped(failed.listed, selection) if failed else None,
            ),
            children=node_page.Children(
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
            dev=viewer.dev,
        )
    )
