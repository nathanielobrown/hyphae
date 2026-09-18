"""One numbered page of a statement that limits nothing itself, and the count a page carries.

A statement a report cites whole cannot carry a viewer's LIMIT, so a repository wraps it:
`window` cuts one page around it, ordered by a cursor column, and stamps every row with how
many matched before the cut. A row the statement gives no cursor value is outside every page
and outside the count, and `cursorless_rows` reads those on their own, under a cap. A
statement that limits itself computes the same count under the same name, and `listed` reads
it off the rows either way.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from hyphae.models.citation import Citation, ParamValue
from hyphae.models.listing import Listed
from hyphae.store import library
from hyphae.store.library import Counted

if TYPE_CHECKING:
    # The handle hands out the repositories that page through here, so the name is the
    # checker's only.
    from hyphae.store.handle import Store

# The column both turn timelines are ordered by: unique and ascending within one thread, and
# NULL on the row standing for the calls that answer no turn, which rides no page of them.
TURN_CURSOR = "turn_index"

# The one name for how many rows matched before a LIMIT bit, wherever that count is computed:
# by the statement itself where it limits its own rows, and by `window` where it limits nothing
# and a repository wraps it. One name is what lets `listed` read the count without knowing which
# statement it came from — and the two ways of computing it never meet, because a statement
# that limits itself is never one `window` wraps.
MATCHED_ROWS = "matched_rows"


def window(
    store: "Store",
    name: str,
    cursor: str,
    skipped: int,
    size: int,
    **bindings: ParamValue,
) -> list[dict[str, Any]]:
    """One numbered page of a library statement that limits nothing itself.

    Rows come back ordered by `cursor`, which is a column name this package supplies — never
    request text — while `skipped` and `size` bind. A row the statement gives no cursor value
    is outside every page and outside the count (`cursorless_rows`).
    """
    return library.fetch(
        store,
        f"SELECT *, count(*) OVER () AS {MATCHED_ROWS} FROM ({library.core(name)})"
        f" WHERE {cursor} IS NOT NULL ORDER BY {cursor} LIMIT $size OFFSET $skipped",
        {"skipped": skipped, "size": size, **bindings},
    )


def cursorless_rows(
    store: "Store",
    name: str,
    cursor: str,
    limit: int,
    **bindings: ParamValue,
) -> list[dict[str, Any]]:
    """The rows a windowed statement gives no cursor value, which no window can reach.

    The timelines' unattributed row is the case: it stands for the calls that answer no turn,
    so it has no turn index and rides the last page instead. `limit` is what the page that
    renders them budgeted; a statement answering with more raises, because these rows arrive
    outside the size the reader asked for and a page that serves them anyway is a page whose
    ceiling was computed against something else.
    """
    rows = library.fetch(
        store,
        f"SELECT * FROM ({library.core(name)}) WHERE {cursor} IS NULL LIMIT $cursorless",
        {"cursorless": limit + 1, **bindings},
    )
    if len(rows) > limit:
        raise ValueError(f"{name} gave more than {limit} row(s) with no {cursor}")
    return rows


def listed[C: Counted](rows: Sequence[C], citation: Citation) -> Listed[C]:
    """A page of rows and the size of the level it came from: every paging statement answers
    `MATCHED_ROWS`, so a page knows the whole level without a second read."""
    return Listed(list(rows), library.matched(rows), citation)
