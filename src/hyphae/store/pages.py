"""Reading the trace store for one request: the queries, and a page of rows.

Every read here runs through the `Store` a request holds (`store/handle.py`): the page's own
open is the route's, and what this module owns is what it asks once it has one.

The three enums are what is left of the viewer's query catalog once each repository takes
its statements (`store/handle.py`), split by what a query is allowed to select: a page or a
fragment truncates every fat column in SQL, and a per-value query is the declared exception.
The payload scans (`tests/view/test_bounds.py`) run over the catalog itself, so a statement
that leaves an enum for a repository stays scanned.

The SQL a page composes around one of those queries is here too: `window` for a numbered page
of a query that limits nothing itself. The session list's sort, filter and cut are its
repository's (`store/sessions.py`), and the records browser's keyset page is its own
(`store/records.py`). A route reads rows; it does not build SQL.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, NamedTuple

from hyphae.models.citation import ParamValue
from hyphae.store import library
from hyphae.store.handle import Store

Row = dict[str, Any]

# The column both turn timelines are ordered by: unique and ascending within one thread, and
# NULL on the row standing for the calls that answer no turn, which rides no page of them.
TURN_CURSOR = "turn_index"


class Page(StrEnum):
    """The library queries the pages are built from, by the part each one fills.

    Grouped under a heading naming the repository that takes each over. A PR of phase 4
    deletes the members under its heading and leaves the heading standing, so two PRs' edits
    always have an unchanged line between them and rebase past each other in either order
    (`plans/store-layering/phase-4-repositories.md`).
    """

    # SessionRepository

    # RecordRepository and OffloadRepository

    # FailureRepository
    # Every failed tool call of one session, across every thread — the one page the NavTree
    # cannot lead to, because a failure is scattered rather than nested (`view/failures.py`).
    SESSION_ERRORS = "view_session_errors"

    # EnrichmentRepository
    # What an enrichment pass said about the session, its turns and its runs. Absent from a
    # store no pass has written to, for the same reason as `sessions.DESCRIBED_SESSIONS`.
    ENRICHMENT = "view_enrichment"

    # NodeRepository
    # One node read whole, the header of its own page. One per kind that has fields of its
    # own; a bucket has none, and a compaction reads out of `view_compactions`.
    RUN_HEADER = "view_run_header"
    TURN_HEADER = "view_turn_header"
    CALL_HEADER = "view_call_header"
    TOOL_HEADER = "view_tool_header"
    # The line each of a thread's turns was read from — what turns a timeline row into a link
    # into the records page.
    TURN_RECORDS = "view_turn_records"

    # NavRepository
    # The levels of the NavTree beside a node page: one thin row per child, whatever the level
    # holds. One query per kind of child rather than per kind of parent, so a turn's calls
    # are read the same way under a session, under a run, or under a bucket.
    NAV_TREE_TURNS = "view_nav_tree_turns"
    NAV_TREE_CALLS = "view_nav_tree_calls"
    NAV_TREE_TOOLS = "view_nav_tree_tools"
    RUNS = "view_runs"
    # The two turn timelines, shared with `hp query` — the same rows a report cites.
    # One query per thread kind: `session_timeline` reads `main`, `run_timeline` a bound source.
    TIMELINE = "session_timeline"
    RUN_TIMELINE = "run_timeline"
    COMPACTIONS = "view_compactions"


class Fragment(StrEnum):
    """The library queries htmx fetches a page of at a time, on expanding something."""

    # NodeRepository
    # One page of the api calls under a turn, and one page of the tool calls under a call.
    TURN_CALLS = "view_turn_calls"
    CALL_TOOLS = "view_call_tools"
    # The numbers behind one NavTree row, fetched when a reader points at it: what the row draws
    # as a bar and a badge, written out. One query for every kind made of api calls, and one
    # apiece for the two kinds made of none — the tool call and the compaction.
    NUMBERS = "view_numbers"
    TOOL_NUMBERS = "view_numbers_tool"
    COMPACTION_NUMBERS = "view_numbers_compaction"


class Value(StrEnum):
    """The library queries that fetch one whole value: the exception to the page bound.

    Every other query truncates in SQL. These return a fat column untruncated because the
    unit *is* one value — the bound is the largest single value in the store, not a page's
    worth of them, and it is only reached when a reader opens that one value. Grouped the way
    `Page` is.
    """

    # NodeRepository
    # The ten values a node's pane previews out of its header and fetches whole here.
    CALL_TEXT = "view_call_text"
    CALL_THINKING = "view_call_thinking"
    # What one tool call was asked and what it returned, one value each rather than the row
    # whole: a pane previews the two apart, so each has its own way to the rest of it.
    TOOL_INPUT = "view_tool_input"
    TOOL_RESULT = "view_tool_result"
    # And what a `Bash` call ran, which the input holds escaped onto one line: a value of its
    # own because a shell command is read as shell, not as a string inside JSON.
    TOOL_COMMAND = "view_tool_command"
    # What a turn was asked, what followed the command a slash turn ran, and what an agent
    # run was briefed with. Each is a value a pane previews, cut in the node's header query
    # and fetched whole here.
    TURN_PROMPT = "view_turn_prompt"
    TURN_COMMAND_ARGS = "view_turn_command_args"
    RUN_BRIEF = "view_run_brief"
    # And the two a run's page reads off the call that spawned it: what that call asked for,
    # and what it returned to the agent that made it.
    RUN_PROMPT = "view_run_prompt"
    RUN_RESULT = "view_run_result"
    # One raw record whole, as the records page previewed it.
    RECORD = "view_record"

    # EnrichmentRepository
    # The two lines an enrichment pass wrote about an item, at each of the three levels it
    # writes at. Fat for the same reason the rest are — a pass writes as much as it wants
    # to — and one query each, because a fetch serves one value and a reader opens whichever
    # of the two ran past the width.
    TURN_DESCRIPTION = "view_turn_description"
    TURN_FRICTION = "view_turn_friction"
    RUN_DESCRIPTION = "view_run_description"
    RUN_FRICTION = "view_run_friction"
    SESSION_DESCRIPTION = "view_session_description"
    SESSION_FRICTION = "view_session_friction"


# Any of the three, for the fetch helper they share.
Library = Page | Fragment | Value


def fetch(store: Store, sql: str, bindings: Mapping[str, ParamValue]) -> list[Row]:
    """`library.fetch`, under the name this module's readers and a test's watch know it by."""
    return library.fetch(store, sql, bindings)


def page_rows(store: Store, page: Library, **bindings: ParamValue) -> list[Row]:
    """The rows of one library query, bound as given."""
    return fetch(store, library.load(page), bindings)


class Listed(NamedTuple):
    """One numbered page of a level: the rows, and how many the level holds in all.

    `total` is the count before the LIMIT bit, which is what lets a page say which of how many
    it is — and what lets a heading count the level rather than the rows in front of the reader.
    """

    rows: list[Row]
    total: int


# The one name for how many rows matched before a LIMIT bit, wherever that count is computed:
# by the query itself where it limits its own rows, and by `window` where it limits nothing and
# the viewer wraps it. One name is what lets a route read the count without knowing which query
# it came from — and the two ways of computing it never meet, because a query that limits itself
# is never one `window` wraps.
MATCHED_ROWS = "matched_rows"


def window(
    store: Store,
    page: Library,
    cursor: str,
    skipped: int,
    size: int,
    **bindings: ParamValue,
) -> Listed:
    """One numbered page of a library query that limits nothing itself.

    The session list's composition (`store/sessions.py`) is the other case: a query whose whole
    result a report quotes cannot carry a viewer's LIMIT, so the viewer wraps it. Rows
    come back ordered by `cursor`, which is a column name this package supplies — never
    request text — while `skipped` and `size` bind. A row the query gives no cursor value is
    outside every page and outside the count (`cursorless_rows`).
    """
    rows = fetch(
        store,
        f"SELECT *, count(*) OVER () AS {MATCHED_ROWS} FROM ({library.core(page)})"
        f" WHERE {cursor} IS NOT NULL ORDER BY {cursor} LIMIT $size OFFSET $skipped",
        {"skipped": skipped, "size": size, **bindings},
    )
    return listed(rows)


def cursorless_rows(
    store: Store,
    page: Library,
    cursor: str,
    limit: int,
    **bindings: ParamValue,
) -> list[Row]:
    """The rows a paged query gives no cursor value, which no window can reach.

    The timelines' unattributed row is the case: it stands for the calls that answer no turn,
    so it has no turn index and rides the last page instead. `limit` is what the page that
    renders them budgeted; a query answering with more raises, because these rows arrive
    outside the size the reader asked for and a page that serves them anyway is a page whose
    ceiling was computed against something else.
    """
    rows = fetch(
        store,
        f"SELECT * FROM ({library.core(page)}) WHERE {cursor} IS NULL LIMIT $cursorless",
        {"cursorless": limit + 1, **bindings},
    )
    if len(rows) > limit:
        raise ValueError(f"{page} gave more than {limit} row(s) with no {cursor}")
    return rows


def listed(rows: list[Row]) -> Listed:
    """A page of rows and the size of the level it came from, out of the query's own count.

    Every paging query carries `MATCHED_ROWS`: how many rows matched before the LIMIT, computed
    with a window function — so a page knows the whole level without a second query, and a level
    whose page is empty is one whose pages ran out.
    """
    return Listed(rows, rows[0][MATCHED_ROWS] if rows else 0)


def dropped(rows: list[Row]) -> int:
    """How many rows the query's own LIMIT left off, for a page that says so rather than lose them.

    A count of rows, not a shortened string: `format.cut` and the `cut` SQL macro are the other
    thing that word means here. Zero on an empty page — a level with nothing in it lost nothing.
    """
    return listed(rows).total - len(rows)
