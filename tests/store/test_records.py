"""`RecordRepository`: one page of a thread's raw records, as models, at a keyset cursor.

Driven against the corpus store, over the seam a page reads through: a row reaches its model
unchanged under the strict build, the cursor pages a thread without repeating or skipping a
line, the method binds exactly what its statement declares, and it hands back the citation
a footer prints. The thread is the corpus's densest (`tests/conftest.py:ANCESTOR`, 47 lines
on `main`), so a page boundary is a real overflow of recorded data rather than a staged one.

The `HYPHAE_LIVE_STORE` leaf at the end is the backstop over real shapes, as in
`tests/store/test_sessions.py`: off by default, run by hand before a PR touching a model opens.
"""

import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation
from hyphae.models.record import Paged, Record
from hyphae.store import library, records
from hyphae.store.handle import Store, open_store
from hyphae.store.records import RecordRepository
from hyphae.store.trace_store import DuckDbExporter
from hyphae.view import bounds
from tests.conftest import ANCESTOR, MAIN, NO_WAIT
from tests.store.test_sessions import LIVE_STORE, rows_of

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")

# The one surface the records browser prints at, as the mapping a page passes.
RECORDS = bounds.RECORDS_WIDTHS._asdict()
# How many lines the densest fixture thread holds; the page tests pin the same number.
LINES = 47


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> RecordRepository:
    return store.records


def thread(repository: RecordRepository, after: int, size: int) -> Paged:
    """The fixture's densest thread, paged as a records URL would page it."""
    return repository.page(session_id=ANCESTOR, source=MAIN, after=after, size=size, widths=RECORDS)


def test_the_handle_hands_out_one_repository(store: Store) -> None:
    """`store.records` is the repository over that store, built once."""
    assert store.records is store.records
    assert isinstance(store.records, RecordRepository)
    assert store.records.store is store


# --- row to model ---------------------------------------------------------------------------


def test_a_record_row_reaches_its_model_unchanged(
    store: Store, repository: RecordRepository
) -> None:
    """A page of records is the statement's rows, one strict model per row, with its citation."""
    page = thread(repository, library.FIRST_PAGE, LINES)
    bindings = library.bind(
        records.RECORDS,
        RECORDS,
        {},
        session_id=ANCESTOR,
        source=MAIN,
        after=library.FIRST_PAGE,
        page_records=LINES,
    )
    raw = rows_of(store, library.load(records.RECORDS), bindings)
    assert len(raw) == LINES, "the densest fixture thread moved: re-pick the session"
    assert [asdict(row) for row in page.rows] == raw
    assert page.citation == Citation(records.RECORDS, bindings)


# --- the values ------------------------------------------------------------------------------


def test_the_first_record_of_the_densest_thread(repository: RecordRepository) -> None:
    """One record whole, as the store archived it: the `mode` line Claude Code opens with,
    which carries neither a uuid nor a timestamp — so both are `None` on the model."""
    page = thread(repository, library.FIRST_PAGE, 1)
    assert page.rows == [
        Record(
            line_no=1,
            uuid=None,
            type="mode",
            timestamp=None,
            raw_chars=87,
            raw_head='{"type": "mode", "mode": "normal", "sessionId": "' + ANCESTOR + '"}',
            matched_rows=LINES,
        )
    ]
    assert page.citation == Citation(
        records.RECORDS,
        {
            "session_id": ANCESTOR,
            "source": MAIN,
            "after": library.FIRST_PAGE,
            "page_records": 1,
            "preview_chars": 160,
        },
    )


def test_a_thread_pages_by_line_number_without_repeating_or_skipping(
    repository: RecordRepository,
) -> None:
    """Following the cursor each page hands back covers the thread exactly, and every page
    says how many lines the cursor still had ahead of it."""
    first = thread(repository, library.FIRST_PAGE, 20)
    assert [row.line_no for row in first.rows] == list(range(1, 21))
    # The count behind the page is what the statement matched past the cut, and the cursor
    # is the last line shown — the next page starts one past it, never on it.
    assert (first.more, first.after) == (27, 20)
    second = thread(repository, 20, 20)
    assert [row.line_no for row in second.rows] == list(range(21, 41))
    assert (second.more, second.after) == (7, 40)
    # The last page: fewer rows than asked for, nothing behind it, and no cursor to resume at.
    last = thread(repository, 40, 20)
    assert [row.line_no for row in last.rows] == list(range(41, 48))
    assert (last.more, last.after) == (0, None)
    # ...and the three pages together are the thread, once and in order.
    assert [row.line_no for page in (first, second, last) for row in page.rows] == list(
        range(1, LINES + 1)
    )


def test_a_page_the_size_of_the_thread_is_the_thread(repository: RecordRepository) -> None:
    """Asked for as many lines as the thread holds, one page is the whole thread and cut nothing."""
    whole = thread(repository, library.FIRST_PAGE, LINES)
    assert [row.line_no for row in whole.rows] == list(range(1, LINES + 1))
    assert (whole.more, whole.after) == (0, None)
    assert all(row.matched_rows == LINES for row in whole.rows)


@pytest.mark.parametrize(
    ("session_id", "source", "after"),
    [
        (ANCESTOR, MAIN, LINES),
        (ANCESTOR, "not-a-thread", library.FIRST_PAGE),
        ("not-a-session", MAIN, library.FIRST_PAGE),
    ],
    ids=["past the end", "unknown thread", "unknown session"],
)
def test_a_cursor_past_the_end_and_a_thread_the_store_lacks_page_empty(
    repository: RecordRepository, session_id: str, source: str, after: int
) -> None:
    """The same answer for both — no rows, nothing behind them, nowhere to resume — which the
    page turns into its 404 rather than rendering empty."""
    page = repository.page(
        session_id=session_id, source=source, after=after, size=20, widths=RECORDS
    )
    assert page == Paged(rows=[], more=0, after=None, citation=page.citation)


def test_a_store_nothing_was_extracted_into_pages_empty(tmp_path: Path) -> None:
    """A store with the schema and no sessions answers empty, and refuses nothing."""
    db = tmp_path / "traces.duckdb"
    DuckDbExporter(db, wait=NO_WAIT)
    with open_store(db, read_only=True, wait=NO_WAIT) as store:
        page = thread(store.records, library.FIRST_PAGE, 20)
        assert page == Paged(rows=[], more=0, after=None, citation=page.citation)


# --- refusals --------------------------------------------------------------------------------

# The one method, with one whole call, so a keyword can be dropped from it or added to it.
CALL: dict[str, Any] = {
    "session_id": ANCESTOR,
    "source": MAIN,
    "after": library.FIRST_PAGE,
    "size": 1,
    "widths": RECORDS,
}


def test_a_keyword_left_off_or_added_is_refused(repository: RecordRepository) -> None:
    """The method binds exactly what its statement declares, keyword by keyword: a drifted
    signature fails here before any page runs."""
    # Untyped, so the checker lets a call drift the way a page's could.
    page: Callable[..., Any] = repository.page
    # The whole call runs...
    page(**CALL)
    # ...one keyword short, it does not...
    with pytest.raises(TypeError, match="missing"):
        page(**{key: value for key, value in CALL.items() if key != "widths"})
    # ...nor with one it never named...
    with pytest.raises(TypeError, match="unexpected keyword"):
        page(**CALL, turn_id="t")
    # ...nor positionally: the keywords are the contract.
    with pytest.raises(TypeError, match="positional"):
        page(*CALL.values())


def test_a_surface_short_of_the_preview_width_is_refused_by_the_binder(
    repository: RecordRepository,
) -> None:
    """The widths are held to the statement too, in the binder's own words."""
    short: dict[str, Any] = {**CALL, "widths": {}}
    with pytest.raises(ValueError, match="binds preview_chars"):
        repository.page(**short)


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_every_thread_of_the_real_archive_builds_every_record(tmp_path: Path) -> None:
    """Every record of every thread, over the archive on this machine, under the strict build.

    Counts only: a record's head is session content, and a failing assertion prints its
    operands. The archive is copied first, with its write-ahead log: a reader holding the
    archive open blocks the extract that writes it.
    """
    archive = Path(os.environ[LIVE_STORE])
    copy = tmp_path / archive.name
    shutil.copy(archive, copy)
    wal = archive.with_name(f"{archive.name}.wal")
    if wal.exists():
        shutil.copy(wal, copy.with_name(f"{copy.name}.wal"))
    with open_store(copy, read_only=True, wait=NO_WAIT) as store:
        threads = rows_of(
            store,
            "SELECT session_id, source, count(*) AS lines FROM raw_records GROUP BY ALL",
            {},
        )
        assert threads, "the archive holds no thread, so this leaf proved nothing"
        built = 0
        for one in threads:
            page = store.records.page(
                session_id=one["session_id"],
                source=one["source"],
                after=library.FIRST_PAGE,
                size=one["lines"],
                widths=RECORDS,
            )
            assert (len(page.rows), page.more, page.after) == (one["lines"], 0, None)
            built += len(page.rows)
    assert built == sum(one["lines"] for one in threads)
