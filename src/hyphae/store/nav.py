"""The NavTree's reads: the three levels under a node, and a session's runs.

`NavRepository` is the seam: the NavTree calls `level` with the model of the level it lays out
and the keys the level's statement binds, at the NavTree's widths, and reads the level whole;
the node browser calls `runs` once per page for every agent run of the session, which is what
the tree hangs the runs and the unattached bucket off. The timelines' bucket row and a
thread's compactions are the node page's own reads (`store/nodes.py`).
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from hyphae.models.citation import Citation, ParamValue
from hyphae.models.listing import Answer
from hyphae.models.nav import NavCallRow, NavToolRow, NavTurnRow, RunRow
from hyphae.store import library

if TYPE_CHECKING:
    # The handle hands out this repository, and this repository holds the handle: the one cycle
    # the design has, so the name is the checker's only.
    from hyphae.store.handle import Store

# The statement that reads one NavTree level, by the row model it lays out: a thread's turns;
# the api calls under a turn — or, at `turn_id` NULL, a thread's unattributed bucket; and the
# tool calls under an api call — or, at `api_call_id` NULL, under a whole turn. None limits
# itself: a level is laid out whole, and `bounds.NAV_TREE_ROW_BYTES` prices the row.
LEVELS: dict[type[NavTurnRow | NavCallRow | NavToolRow], str] = {
    NavTurnRow: "view_nav_tree_turns",
    NavCallRow: "view_nav_tree_calls",
    NavToolRow: "view_nav_tree_tools",
}
RUNS = "view_runs"


class NavRepository:
    """The NavTree's reads, over one open store: `store.nav`.

    The keys ride as one mapping because which keys a level has is the level's business
    (`view/pages/node/nav_tree.py`), and the widths are a keyword-only mapping
    (`bounds.NAV_TREE_WIDTHS._asdict()`); `library.bind` fills what the statement declares
    and refuses the rest. A plain class rather than a dataclass: mutmut skips every decorated
    class, and the handle builds one of these per store anyway.
    """

    def __init__(self, store: "Store") -> None:
        self.store = store

    def level[L: NavTurnRow | NavCallRow | NavToolRow](
        self, model: type[L], keys: Mapping[str, ParamValue], *, widths: Mapping[str, int]
    ) -> Answer[L]:
        """One level of the NavTree whole, as the model that keyed it, in the statement's order."""
        statement = LEVELS[model]
        bindings = library.bind(statement, widths, {}, **keys)
        rows = library.fetch(self.store, library.load(statement), bindings)
        return Answer([model(**row) for row in rows], Citation(statement, bindings))

    def runs(self, *, session_id: str, widths: Mapping[str, int]) -> Answer[RunRow]:
        """Every agent run of one session in the order they started, each with the call that
        spawned it — or none, which is what makes it unattached."""
        bindings = library.bind(RUNS, widths, {}, session_id=session_id)
        rows = library.fetch(self.store, library.load(RUNS), bindings)
        return Answer([RunRow(**row) for row in rows], Citation(RUNS, bindings))
