"""The sessions and the projects: what the list, the landing page and a session's header read.

`SessionRepository` is the seam: a page calls a method with the keys and the widths its
surface prints at, and reads models back with the citation its footer quotes. Every method
binds exactly what its statement declares and builds each row by column name, so a
statement that drifts from its model fails here rather than on a page.

The session list's composition is here too, and nowhere else: a `?sort=` column and a filter
predicate cannot be bound parameters, so the library query stays the citable core and what
follows wraps it. `SORTS`, `FILTERS` and `DIRECTIONS` are closed, so a key outside them is a
`KeyError` here and a 400 at the route (`view/pages/sessions/routes.py`) and never a fragment
of SQL — every value a request supplied binds as a parameter, and no request text reaches
DuckDB as text.
"""

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from hyphae.models.citation import Citation, ParamValue
from hyphae.models.listing import (
    Answer,
    DescribedSessionRollup,
    Listing,
    Project,
    ProjectRollup,
    ProjectRollups,
    SessionHeader,
    SessionRollup,
)
from hyphae.projects import project_predicate
from hyphae.store import library

if TYPE_CHECKING:
    # The handle hands out this repository, and this repository holds the handle: the one cycle
    # the design has, so the name is the checker's only.
    from hyphae.store.handle import Store

# The statements this repository reads, by the stem the library loads each under.
# Every session in the store, one row: what the list ranks and drills from.
SESSIONS = "view_sessions"
# What the pass said each session was, joined to the page of rows the list just read. Absent
# from a store no pass has written to, which is why `view/enrichment.py` asks first.
DESCRIBED_SESSIONS = "view_described_sessions"
# The names the list's project filter offers, which is a column of the store rather than of
# the page: the projects on one page of sessions are not the projects to filter by.
PROJECTS = "view_projects"
# Every project the store holds sessions for, which is the landing page: the counts a reader
# lands on are a corpus's, so they come from the `corpus_*` views.
PROJECT_ROLLUPS = "view_project_rollups"
SESSION_HEADER = "view_session_header"

# What the session list can be sorted by: columns of `view_sessions`, in the order the page
# heads them. Closed, and the only place a request's `sort` value is ever looked up — an
# unknown key is a 400, never a fragment of SQL. `tests/view/test_app__list.py` checks every
# one against the columns the query returns, and the page's labels against this list
# (`view/pages/sessions/models.py:HEADINGS`). Output tokens and active time are not here: they
# ride the row as the second line of the cost and wall cells, and a column nobody ranks a
# corpus by is texture rather than a heading.
SORTS: tuple[str, ...] = (
    "started_at",
    "title",
    "project_dir",
    "turns",
    "api_calls",
    "tool_calls",
    "compactions",
    # By the count, though the cell shows the rate: one tool call that failed is a session at
    # 100%, and not the session a reader sorting by errors is looking for.
    "tool_errors",
    "cost_usd",
    "wall_ms",
    "agent_runs",
)


@dataclass(frozen=True)
class Filter:
    """One way the session list can be narrowed, as the two halves that make it safe."""

    # The predicate composed into the WHERE, naming its own bound parameter and nothing else.
    # It reads a column of `view_sessions`, which is what the composition wraps.
    predicate: str
    # What a request's value has to parse as before it can bind. A value that will not parse
    # is a 400, so the type is also the only vetting a filter value gets.
    type: library.ParamType


# What the session list can be narrowed by, per query-string key. Closed, like `SORTS`: a key
# outside it is a 400, and a key inside it contributes a fixed predicate and a bound value —
# request text never becomes SQL. Composed in this order, so the WHERE and the citation read
# the same whatever order a URL happened to put them in.
FILTERS: dict[str, Filter] = {
    # A path prefix, not a path: a worktree checkout sits under the repository it was cut
    # from, so filtering by a project has to hold its worktrees' sessions the way the CLI's
    # `--project` does. One statement of the rule, in `hyphae.projects`.
    "project": Filter(project_predicate("project_dir", "$project"), library.ParamType.TEXT),
    "since": Filter("started_at >= $since", library.ParamType.DATE),
    # Inclusive of the day named: someone asking for sessions until the 7th means the 7th.
    "until": Filter("started_at < $until + INTERVAL 1 DAY", library.ParamType.DATE),
    "skill": Filter("list_contains(skills, $skill)", library.ParamType.TEXT),
    # A floor rather than a flag, so `errors=1` reads "any" and a larger number "at least".
    "errors": Filter("tool_errors >= $errors", library.ParamType.INTEGER),
}

# The two orderings a reader can ask for, as the SQL keyword each one puts in the ORDER BY.
DIRECTIONS: dict[str, str] = {"asc": "ASC", "desc": "DESC"}

# What one row of the list shows of the values a transcript wrote: each string cut to a head,
# the skills and the agent types cut to their first few with a count of what was left, and the
# PR links the page has no column for dropped. Composed here rather than in the query because
# the list's filters read the whole values — a `project` matched against a cut path would miss
# every session under a longer one, and a `skill` outside the first few would find nothing —
# and applied outside the window, so it cuts the rows one page shows and nothing else.
#
# The `cut` macro takes one character more than the row prints, which is how the component
# knows a value was stopped rather than ended and marks it (`view/text/format.py:cut`). It is a
# macro of the library, so this runs only on a connection `macros.install` has seen — which
# every `Store` is (`store/handle.py:open_store`), and so is every fixture that reaches here.
SHOWN = """SELECT * EXCLUDE (pr_urls) REPLACE (
    cut(title, $head_chars) AS title,
    cut(project_dir, $head_chars) AS project_dir,
    list_transform(list_slice(coalesce(skills, []), 1, $head_items),
        name -> cut(name, $item_chars)) AS skills,
    list_slice(coalesce(agent_types, []), 1, $head_items) AS agent_types
), greatest(len(coalesce(skills, [])) - $head_items, 0) AS skills_cut,
   greatest(len(coalesce(agent_types, [])) - $head_items, 0) AS agent_types_cut FROM"""
# The three widths `SHOWN` binds, read off the surface by name: the composition has no file
# to fill them from, and the library query under it binds `item_chars` again.
SHOWN_WIDTHS = ("head_chars", "item_chars", "head_items")

# How many rows past the page the list reads: enough to know whether there is another page,
# never enough to show one. `listing` is the only place it is spent, and the citation under
# the page quotes the size the reader asked for instead.
PAGER_PROBE = 1


def composed(
    sort: str, direction: str, filters: Mapping[str, ParamValue], *, described: bool
) -> str:
    """The session list's statement: one of `SORTS` over the core, under `FILTERS`, cut by `SHOWN`.

    The library query goes in a subquery untouched, and what is wrapped around it is a WHERE
    of `FILTERS` predicates, an ORDER BY from a checked sort and direction, a LIMIT, and
    `SHOWN` over the rows that survive all three. `session_id` breaks ties in the same
    direction, which makes every sort a total order, its reverse exact, and the page
    boundaries stable between requests. The rows carrying no value sort last either way:
    "the store does not know" is not the largest reading of a column, or the smallest.
    """
    # A sort or filter key *is* part of a SQL fragment, so membership is the whole guard —
    # and it is checked here as well as at the route, because this builds the SQL.
    if sort not in SORTS or not filters.keys() <= FILTERS.keys():
        raise KeyError(sort)
    keyword = DIRECTIONS[direction]
    # What the pass said each session was, joined before the sort so a row carries it: the
    # left join adds columns and never a row, so it changes neither the order nor the count.
    joined = (
        f" LEFT JOIN ({library.core(DESCRIBED_SESSIONS)}) USING (session_id)" if described else ""
    )
    # `FILTERS` order, not the query string's: the SQL a citation stands for is the same
    # whichever way a URL was typed.
    applied = [FILTERS[key].predicate for key in FILTERS if key in filters]
    where = f" WHERE {' AND '.join(applied)}" if applied else ""
    return (
        f"{SHOWN} (SELECT * FROM ({library.core(SESSIONS)}){joined}{where}"
        f" ORDER BY {sort} {keyword} NULLS LAST, session_id {keyword}"
        " LIMIT $limit OFFSET $offset)"
    )


class SessionRepository:
    """The session reads, over one open store: `store.sessions`.

    Every method is keyword-only, one keyword per key its statement binds, with the surface's
    widths as one mapping (`bounds.LIST_WIDTHS._asdict()`); `library.bind` fills what the
    statement declares and refuses the rest. A plain class rather than a dataclass: mutmut
    skips every decorated class, and the handle builds one of these per store anyway.
    """

    def __init__(self, store: "Store") -> None:
        self.store = store

    def listing(
        self,
        *,
        sort: str,
        direction: str,
        page: int,
        size: int,
        filters: Mapping[str, ParamValue],
        widths: Mapping[str, int],
        described: bool,
    ) -> Listing:
        """One page of the session list, ordered by one of `SORTS` and narrowed by `FILTERS`.

        `described` says whether the store holds the enrichment tables to join — a caller asks
        `view/enrichment.py`, where that catalog check lives. It is an argument rather than a
        check here because it is a fact about the store, not about the request. Joined, every
        row is a `DescribedSessionRollup`; a page narrows by `isinstance`.
        """
        # What the list binds, composed once and cited below out of the same mapping: a
        # citation that drifted from its query is a false one. The joined query cuts its own
        # strings at the same widths, and is cited on its own.
        listed: dict[str, ParamValue] = {
            "limit": size,
            "offset": (page - 1) * size,
            **{width: widths[width] for width in SHOWN_WIDTHS},
            **filters,
        }
        joined = library.bind(DESCRIBED_SESSIONS, widths, {}) if described else {}
        # The one place the query and the citation under it differ, and deliberately: reading a
        # row past the page is cheaper than a second query and all a pager needs to know there
        # is another one, while a footer quoting that limit would offer a row the page never
        # showed.
        rows = library.fetch(
            self.store,
            composed(sort, direction, filters, described=described),
            {**listed, **joined, "limit": size + PAGER_PROBE},
        )
        model = DescribedSessionRollup if described else SessionRollup
        # The sort and the direction are the composition's own and bind nothing, so they are
        # stated on the citation rather than bound.
        ran = [Citation(SESSIONS, {"sort": sort, "direction": direction, **listed})]
        if described:
            ran.append(Citation(DESCRIBED_SESSIONS, joined))
        return Listing([model(**row) for row in rows[:size]], len(rows) > size, ran)

    def projects(self, *, widths: Mapping[str, int]) -> Answer[Project]:
        """The projects the filter box suggests: the busiest, each path whole."""
        bindings = library.bind(PROJECTS, widths, {})
        rows = library.fetch(self.store, library.load(PROJECTS), bindings)
        return Answer([Project(**row) for row in rows], Citation(PROJECTS, bindings))

    def rollups(self, *, as_of: dt.date, widths: Mapping[str, int]) -> ProjectRollups:
        """Every project's history and two trailing windows measured back from `as_of`.

        `cut` is how many projects the statement's own limit left off: what the landing page
        says rather than loses.
        """
        bindings = library.bind(PROJECT_ROLLUPS, widths, {}, as_of=as_of)
        rows = [
            ProjectRollup(**row)
            for row in library.fetch(self.store, library.load(PROJECT_ROLLUPS), bindings)
        ]
        cut = rows[0].matched_rows - len(rows) if rows else 0
        return ProjectRollups(rows, cut, Citation(PROJECT_ROLLUPS, bindings))

    def header(self, *, session_id: str, widths: Mapping[str, int]) -> SessionHeader | None:
        """One session's header, or None when the store holds no session by that id."""
        bindings = library.bind(SESSION_HEADER, widths, {}, session_id=session_id)
        rows = library.fetch(self.store, library.load(SESSION_HEADER), bindings)
        if not rows:
            return None
        (row,) = rows
        return SessionHeader(citation=Citation(SESSION_HEADER, bindings), **row)
