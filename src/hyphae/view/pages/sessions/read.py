"""Reading one page of the session list out of the store: the page, its suggestions, its cites.

The whole document from one open of the store, closed before anything renders
(`view/deps.py`, the window trade-off). Everything above this module hands it a checked
`ListParams` and reads a typed page back, naming no query, binding or store column.
"""

from collections.abc import Mapping
from pathlib import Path

from hyphae.store.handle import open_store
from hyphae.store.library import ParamValue
from hyphae.store.pages import Page, Row, page_rows, sorted_sessions
from hyphae.store.trace_store import PAGE_WAIT
from hyphae.view import bounds
from hyphae.view.bounds import bound
from hyphae.view.citation import cited
from hyphae.view.enrichment import enriched
from hyphae.view.models import Count
from hyphae.view.pages.sessions.models import Described, ListParams, SessionRow, SessionsPage


def sessions(db: Path, params: ListParams) -> SessionsPage:
    """One page of sessions, under the filter, sort and size the URL carried."""
    with open_store(db, read_only=True, wait=PAGE_WAIT) as store:
        # Whether the store holds the enrichment tables at all, which decides both what the
        # list joins and what it cites: a page cites what it ran.
        describes = enriched(store)
        # What the list binds, composed once and read twice — by the query, and by the
        # citation under it — because a citation that drifted from its query is a false one.
        listed = _list_bound(params.page, params.size, params.filters)
        # The joined query cuts its own strings, and takes the same head a row's other strings
        # do — one surface prints the row. Cited on its own below, out of this same mapping.
        joined = bound(Page.DESCRIBED_SESSIONS, bounds.LIST_WIDTHS) if describes else {}
        rows, more = sorted_sessions(
            store,
            params.sort,
            params.direction,
            params.size,
            params.filters,
            {**listed, **joined},
            described=describes,
        )
        projects = page_rows(store, Page.PROJECTS, **bound(Page.PROJECTS, bounds.LIST_WIDTHS))
    return SessionsPage(
        rows=[_session_row(row) for row in rows],
        # Suggestions for the filter form, not a closed set: the form runs whatever is typed.
        projects=[row["project_dir"] for row in projects],
        describes=describes,
        more=more,
        citations={
            Page.SESSIONS.value: cited(
                Page.SESSIONS,
                # The bindings the query above ran, out of the one mapping it read them from —
                # including the widths, which are composed around the file like the paging is:
                # re-running it alone answers with whole titles, paths and skill lists. The
                # sort and the direction are the composition's own and bind nothing, so they
                # are stated here.
                {"sort": params.sort, "direction": params.direction, **listed},
            ),
            # Joined to that page rather than run against it, so it is cited on its own — and
            # only over a store whose enrichment tables exist to join.
            **(
                {Page.DESCRIBED_SESSIONS.value: cited(Page.DESCRIBED_SESSIONS, joined)}
                if describes
                else {}
            ),
        },
    )


def _list_bound(page: int, size: int, filters: Mapping[str, ParamValue]) -> dict[str, ParamValue]:
    """What one page of the session list binds: its window, its row cut, and its filters.

    The one difference between this and what the query runs is the store's `PAGER_PROBE`,
    added where it is spent (`store/pages.py:sorted_sessions`).
    """
    return {
        "limit": size,
        "offset": (page - 1) * size,
        # Read off the surface a field at a time rather than through `bound`: the statement
        # these three go to is composed in the store, so there is no parameter list to fill
        # from — `SHOWN` binds them, the library query binds `item_chars` again, and the window
        # and the filters are the composition's own.
        "head_chars": bounds.LIST_WIDTHS.head_chars,
        "item_chars": bounds.LIST_WIDTHS.item_chars,
        "head_items": bounds.LIST_WIDTHS.head_items,
        **filters,
    }


def _session_row(row: Row) -> SessionRow:
    """One store row as the row the session list prints.

    The three lists arrive as DuckDB lists and are NULL where the session has none, so each is
    coalesced here — the component prints what it is handed. The enrichment columns are absent
    entirely over a store with no pass to join, which is why they are read with `get`.
    """
    said = row.get("description")
    return SessionRow(
        session_id=row["session_id"],
        started_at=row["started_at"],
        title=row["title"],
        project_dir=row["project_dir"],
        turns=row["turns"],
        api_calls=row["api_calls"],
        tool_calls=row["tool_calls"],
        compactions=row["compactions"],
        tool_errors=row["tool_errors"],
        cost_usd=row["cost_usd"],
        output_tokens=row["output_tokens"],
        unpriced_api_calls=row["unpriced_api_calls"],
        wall_ms=row["wall_ms"],
        active_ms=row["active_ms"],
        agent_types=[Count(kind["name"], kind["runs"]) for kind in row["agent_types"] or []],
        agent_types_cut=row["agent_types_cut"],
        skills=row["skills"] or [],
        skills_cut=row["skills_cut"],
        work=[Count(kind["name"], kind["turns"]) for kind in row.get("work") or []],
        work_cut=row.get("work_cut", 0),
        described=Described(said, row["category"], row["outcome"]) if said else None,
    )
