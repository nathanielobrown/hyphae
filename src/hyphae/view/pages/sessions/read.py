"""Reading one page of the session list out of the store: the page, its suggestions, its cites.

The whole document from one open of the store, closed before anything renders
(`view/deps.py`, the window trade-off). Everything above this module hands it a checked
`ListParams` and reads a typed page back, naming no query, binding or store column.
"""

from pathlib import Path

from hyphae.models.listing import DescribedSessionRollup, SessionRollup
from hyphae.store.handle import open_store
from hyphae.store.trace_store import PAGE_WAIT
from hyphae.view import bounds
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
        listing = store.sessions.listing(
            sort=params.sort,
            direction=params.direction,
            page=params.page,
            size=params.size,
            filters=params.filters,
            widths=bounds.LIST_WIDTHS._asdict(),
            described=describes,
        )
        projects = store.sessions.projects(widths=bounds.LIST_WIDTHS._asdict())
    return SessionsPage(
        rows=[_session_row(row) for row in listing.rows],
        # Suggestions for the filter form, not a closed set: the form runs whatever is typed.
        projects=[project.project_dir for project in projects.rows],
        describes=describes,
        more=listing.more,
        # The list's own query, and the joined one after it over a store whose enrichment
        # tables exist to join — each cited on its own, out of the bindings it ran.
        citations={citation.name: cited(citation) for citation in listing.ran},
    )


def _session_row(row: SessionRollup) -> SessionRow:
    """One store row as the row the session list prints.

    The three lists arrive as DuckDB lists and are NULL where the session has none, so each is
    coalesced here — the component prints what it is handed. The enrichment columns ride the
    row only over a store with a pass to join, which is what the narrowing reads.
    """
    described = None
    work: list[Count] = []
    work_cut = 0
    if isinstance(row, DescribedSessionRollup):
        work = [Count(kind["name"], kind["turns"]) for kind in row.work or []]
        work_cut = row.work_cut or 0
        # Three values or none: the session table holds all three NOT NULL, so a description
        # never rides without its category and outcome.
        if row.description and row.category is not None and row.outcome is not None:
            described = Described(row.description, row.category, row.outcome)
    return SessionRow(
        session_id=row.session_id,
        started_at=row.started_at,
        title=row.title,
        project_dir=row.project_dir,
        turns=row.turns,
        api_calls=row.api_calls,
        tool_calls=row.tool_calls,
        compactions=row.compactions,
        tool_errors=row.tool_errors,
        cost_usd=row.cost_usd,
        output_tokens=row.output_tokens,
        unpriced_api_calls=row.unpriced_api_calls,
        wall_ms=row.wall_ms,
        active_ms=row.active_ms,
        agent_types=[Count(kind["name"], kind["runs"]) for kind in row.agent_types or []],
        agent_types_cut=row.agent_types_cut,
        skills=row.skills or [],
        skills_cut=row.skills_cut,
        work=work,
        work_cut=work_cut,
        described=described,
    )
