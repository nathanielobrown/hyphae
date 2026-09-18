"""Reading the trace store for one request: the queries the NavTree still reads as rows.

Every read here runs through the `Store` a request holds (`store/handle.py`): the page's own
open is the route's, and what this module owns is what it asks once it has one.

`Page` is what is left of the viewer's query catalog once each repository takes its
statements (`store/handle.py`): the NavTree's levels, which `store.nav` takes last. The
payload scans (`tests/view/test_bounds.py`) run over the catalog itself, so a statement that
leaves the enum for a repository stays scanned. The SQL a page composes around a query is a
repository's (`store/paging.py`, `store/sessions.py`, `store/records.py`). A route reads
rows; it does not build SQL.
"""

from enum import StrEnum
from typing import Any

from hyphae.models.citation import ParamValue
from hyphae.store import library
from hyphae.store.handle import Store

Row = dict[str, Any]


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

    # EnrichmentRepository

    # NodeRepository

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


def page_rows(store: Store, page: Page, **bindings: ParamValue) -> list[Row]:
    """The rows of one library query, bound as given."""
    return library.fetch(store, library.load(page), bindings)
