"""`hp query`'s reads: scope the corpus to one project, then run any library statement over it.

`AnalysisRepository` is the seam: the runner calls `scope` with what `--project`, `--since`
and `--as-of` resolved to, which builds the two corpus relations every corpus statement reads
and counts the sessions no predicate can place; then `run` with a statement's name and the
bindings the manifest resolved, and reads `Answered` back — the header, the body, and the
citation naming the corpus ahead of the statement's own bindings.
"""

import datetime as dt
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from hyphae.models.analysis import Answered
from hyphae.models.citation import Citation, ParamValue
from hyphae.projects import project_predicate, resolve_project
from hyphae.store import library

if TYPE_CHECKING:
    # The handle hands out this repository, and this repository holds the handle: the one cycle
    # the design has, so the name is the checker's only.
    from hyphae.store.handle import Store

# The sessions `--project` selects, and the window flag every corpus query reads. Written
# here rather than in each query file so that a query cannot scope itself differently from
# the corpus it reports against. These two relations are `library.CORPUS_RELATIONS`, which is
# what reading one makes a statement a corpus one. Module constants rather than library
# files: a library statement is one `hp query` can name and the query page can show, and
# these are the DDL behind every one of those.
PROJECT_SESSIONS = f"""
CREATE OR REPLACE TEMP TABLE project_sessions AS
SELECT
    id AS session_id,
    started_at,
    coalesce(
        started_at >= $as_of::DATE - to_days($window_days::INTEGER)
            AND started_at < $as_of::DATE + INTERVAL 1 DAY,
        false
    ) AS in_window
FROM sessions
WHERE {project_predicate("project_dir", "$project")}
  AND ($since::DATE IS NULL OR started_at >= $since::DATE)
"""

# The two windows every count is reported in, as rows a count can group by. Written here for
# the same reason as the predicate above: a query that filtered its own window would be a
# second implementation of the recency rule, free to drift from the total it restricts.
SESSION_PERIODS = """
CREATE OR REPLACE TEMP VIEW session_period AS
SELECT session_id, 'corpus' AS period FROM project_sessions
UNION ALL
SELECT session_id, 'trailing_window' AS period FROM project_sessions WHERE in_window
"""

# Sessions no project predicate can place. They are excluded from every corpus count, so the
# runner reports how many there were rather than leaving the gap silent.
UNPLACEABLE = "SELECT count(*) FROM sessions WHERE project_dir IS NULL"


class AnalysisRepository:
    """`hp query`'s reads over one open store: `store.analysis`.

    The corpus relations are temp tables on the connection, so `scope` is state: it holds the
    bindings that built them in `corpus`, and every `run` after it cites those first. A plain
    class rather than a dataclass: mutmut skips every decorated class, and the handle builds
    one of these per store anyway.
    """

    def __init__(self, store: "Store") -> None:
        self.store = store
        # What scoped the corpus, in citation order; empty until `scope` runs.
        self.corpus: dict[str, ParamValue] = {}

    def scope(self, *, project: Path, since: dt.date | None, as_of: dt.date) -> int:
        """Materialize the corpus for `project`, and count the sessions it could not place.

        Those have no `project_dir`, so no predicate selects them and no corpus count includes
        them: the runner reports the count rather than leaving the gap silent.
        """
        self.corpus = {
            "project": str(resolve_project(project)),
            "since": since,
            "as_of": as_of,
            "window_days": library.WINDOW_DAYS,
        }
        # The view reads the table, so the table is built first.
        self.store.rows(PROJECT_SESSIONS, self.corpus)
        self.store.rows(SESSION_PERIODS, {})
        ((unplaceable,),) = self.store.rows(UNPLACEABLE, {}).rows
        return unplaceable

    def run(self, name: str, bindings: Mapping[str, ParamValue]) -> Answered:
        """Run one library statement at `bindings`, whole, with its citation.

        `bindings` are the statement's own, every one resolved by the manifest; the driver
        refuses one it names and the caller left out. A corpus statement needs `scope` first,
        and its citation says what scoped it ahead of what it bound.
        """
        columns, rows = self.store.rows(library.load(name), bindings)
        return Answered(columns, rows, Citation(name, {**self.corpus, **bindings}))
