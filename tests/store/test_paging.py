"""`store/paging.py`: a numbered page cut around a statement that limits nothing itself.

Driven against the corpus store: a window orders by the cursor, skips what the pages before
it held, and stamps every row with how many matched before the LIMIT bit; a row the statement
gives no cursor value rides no page and counts on none, and is read cursorless under a cap
instead; and `listed` reads the count off the rows a self-limiting statement answers.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from hyphae.models.citation import Citation
from hyphae.models.listing import Listed
from hyphae.store import library, paging
from hyphae.store.handle import Store, open_store
from hyphae.view import bounds
from tests.conftest import NO_WAIT, RESUME, SPINE
from tests.store.test_sessions import rows_of

pytestmark = pytest.mark.xdist_group("corpus_store")

TIMELINE = "session_timeline"
LOG = bounds.LOG_WIDTHS._asdict()


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


def test_a_window_orders_by_the_cursor_and_counts_the_level(store: Store) -> None:
    """A page of a statement's rows: ordered by the cursor, cut to the size after the rows the
    pages before it held, and every row carrying how many the level holds in all."""
    bindings = library.bind(TIMELINE, LOG, {}, session_id=SPINE)
    whole = sorted(
        rows_of(store, library.load(TIMELINE), bindings), key=lambda row: row["turn_index"]
    )
    assert len(whole) == 4
    # The second page of two of the spine's four turns...
    rows = paging.window(store, TIMELINE, paging.TURN_CURSOR, 2, 2, **bindings)
    assert rows == [{**row, paging.MATCHED_ROWS: 4} for row in whole[2:4]]
    # ...a page past the level is empty...
    assert paging.window(store, TIMELINE, paging.TURN_CURSOR, 4, 2, **bindings) == []
    # ...and a page wider than the level is the level, counted the same.
    wide = paging.window(store, TIMELINE, paging.TURN_CURSOR, 0, 10, **bindings)
    assert [row["turn_index"] for row in wide] == [0, 1, 2, 3]
    assert {row[paging.MATCHED_ROWS] for row in wide} == {4}


def test_a_row_with_no_cursor_rides_no_page_and_is_read_cursorless_under_a_cap(
    store: Store,
) -> None:
    """A timeline's unattributed row has no turn index: no window reaches it and none counts
    it, so it is read on its own — capped, because it arrives outside the size a reader asked
    for. `RESUME` answers turns that live in the session it resumed, so its timeline is that
    row alone."""
    bindings = library.bind(TIMELINE, LOG, {}, session_id=RESUME)
    assert paging.window(store, TIMELINE, paging.TURN_CURSOR, 0, 10, **bindings) == []
    rows = paging.cursorless_rows(store, TIMELINE, paging.TURN_CURSOR, 1, **bindings)
    assert [row["turn_id"] for row in rows] == [library.UNATTRIBUTED]
    assert rows[0][paging.TURN_CURSOR] is None
    with pytest.raises(
        ValueError, match=r"^session_timeline gave more than 0 row\(s\) with no turn_index$"
    ):
        paging.cursorless_rows(store, TIMELINE, paging.TURN_CURSOR, 0, **bindings)


class Counted(NamedTuple):
    """The one column `listed` reads: a row of a statement that limits itself."""

    matched_rows: int


def test_listed_reads_the_count_off_the_first_row() -> None:
    """A page of rows and the size of the level it came from, off the count every row carries;
    a page that matched nothing is a level of nothing."""
    cited = Citation("view_turn_calls", {"skipped": 0})
    assert paging.listed([Counted(7), Counted(7)], cited) == Listed(
        [Counted(7), Counted(7)], 7, cited
    )
    assert paging.listed([], cited) == Listed([], 0, cited)
