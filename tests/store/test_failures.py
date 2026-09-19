"""`FailureRepository`: every failed tool call of one session, as models, in the order they ran.

Driven against the corpus store, over the seam the errors page and the stepper read through:
a row reaches its model unchanged under the strict build, the order is the statement's, the
cap leaves a count rather than losing rows, the method binds exactly what its statement
declares, and it hands back the citation a footer prints. The fixture corpus records one
failure apiece in two sessions, which is enough for the values but not for an order or a
cut, so those leaves plant `is_error` on every call of `FORK_ORIGIN` — the same seven calls
on two threads the errors page tests plant (`tests/view/pages/errors/test_errors.py`).

The `HYPHAE_LIVE_STORE` leaf at the end is the backstop over real shapes, as in
`tests/store/test_sessions.py`: off by default, run by hand before a PR touching a model opens.
"""

import datetime as dt
import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation
from hyphae.models.failure import Failure, Failures
from hyphae.store import failures, library
from hyphae.store.failures import FailureRepository
from hyphae.store.handle import Store, open_store
from hyphae.store.trace_store import StoreExporter
from hyphae.view import bounds
from tests.conftest import ANCESTOR, FORK_ORIGIN, FORK_RUN, NO_WAIT
from tests.store.test_sessions import LIVE_STORE, rows_of
from tests.view.conftest import planter
from tests.view.pages.errors.test_errors import ALL_FAILED, failed

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")

# The one surface the errors page prints at, as the mapping a page passes.
ERRORS = bounds.ERRORS_WIDTHS._asdict()
# How many tool calls `FORK_ORIGIN` recorded, all of which the planted store fails.
PLANTED = 7


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> FailureRepository:
    return store.failures


@pytest.fixture
def planted(enriched_db: Path, tmp_path: Path) -> Path:
    """The corpus with every tool call of `FORK_ORIGIN` failed: seven, across two threads."""
    return planter(enriched_db, tmp_path)(ALL_FAILED)


def test_the_handle_hands_out_one_repository(store: Store) -> None:
    """`store.failures` is the repository over that store, built once."""
    assert store.failures is store.failures
    assert isinstance(store.failures, FailureRepository)
    assert store.failures.store is store


# --- row to model ---------------------------------------------------------------------------


def test_a_failure_row_reaches_its_model_unchanged(
    store: Store, repository: FailureRepository
) -> None:
    """A session's failures are the statement's rows, one strict model per row, with its
    citation — bound keys first, then the widths, which is the order the footer quotes."""
    answer = repository.failures(session_id=FORK_ORIGIN, widths=ERRORS)
    bindings = library.bind(failures.SESSION_ERRORS, ERRORS, {}, session_id=FORK_ORIGIN)
    raw = rows_of(store, library.load(failures.SESSION_ERRORS), bindings)
    assert raw, "the recorded failure moved: re-pick the session"
    assert [asdict(row) for row in answer.rows] == raw
    assert answer.citation == Citation(failures.SESSION_ERRORS, bindings)
    assert list(answer.citation.bindings) == ["session_id", "nav_chars", "errors"]


# --- the values ------------------------------------------------------------------------------


def test_the_one_failure_the_fork_origin_recorded(repository: FailureRepository) -> None:
    """One failure whole, as the store archived it: an `Agent` call on the fork's own thread,
    with the `tool_fields` struct its title is composed from — every member the macro names,
    the ones this input lacks NULL — and a count of one, because it is the session's only."""
    answer = repository.failures(session_id=FORK_ORIGIN, widths=ERRORS)
    assert answer == Failures(
        rows=[
            Failure(
                source=FORK_RUN,
                tool_call_id="toolu_01QL29AQk8UfeCUq8EsoyPs6",
                name="Agent",
                fields={
                    "path": None,
                    "command": None,
                    "description": "[redacted]",
                    "subagent_type": "[redacted]",
                    "skill": None,
                    "args": None,
                    "to": None,
                    "addressed": None,
                    "summary": None,
                    "pattern": None,
                    "url": None,
                    "query": None,
                    "message": None,
                    "todos": None,
                    "input_head": '{"description": "[redacted]", "subagent_type": "[redacted]",'
                    ' "prompt": "[redacted]"}',
                },
                is_error=True,
                started_at=dt.datetime(2026, 7, 21, 22, 7, 28, 710000, tzinfo=dt.UTC),
                matched_rows=1,
            )
        ],
        cut=0,
        citation=Citation(
            failures.SESSION_ERRORS, {"session_id": FORK_ORIGIN, "nav_chars": 110, "errors": 100}
        ),
    )


def test_a_session_that_failed_on_two_threads_lists_every_failure_in_the_order_they_happened(
    planted: Path,
) -> None:
    """The list spans the whole session, in the total order the statement states: the clock,
    then the thread, its index and its id — so a page that cut the tail cut the same rows twice
    running."""
    with open_store(planted, read_only=True, wait=NO_WAIT) as store:
        answer = store.failures.failures(session_id=FORK_ORIGIN, widths=ERRORS)
        # The expectation spells the order itself, in SQL over the planted rows...
        order = failed(store._connection, FORK_ORIGIN)
    assert [(row.source, row.tool_call_id) for row in answer.rows] == order
    assert len(order) == PLANTED
    # ...more than one thread among them, which is what makes the list session-wide...
    assert len({row.source for row in answer.rows}) > 1
    # ...and under the cap, so nothing was cut, and every row carries the whole count.
    assert answer.cut == 0
    assert all(row.matched_rows == PLANTED for row in answer.rows)


def test_a_cap_below_the_count_keeps_the_first_failures_and_counts_the_rest(
    planted: Path,
) -> None:
    """Capped at three, the answer is the first three of the same order, and says how many
    the cap left off rather than reading as the whole list."""
    with open_store(planted, read_only=True, wait=NO_WAIT) as store:
        capped = store.failures.failures(session_id=FORK_ORIGIN, widths={**ERRORS, "errors": 3})
        whole = store.failures.failures(session_id=FORK_ORIGIN, widths=ERRORS)
    assert capped.rows == whole.rows[:3]
    assert capped.cut == PLANTED - 3
    assert capped.citation.bindings["errors"] == 3


@pytest.mark.parametrize(
    "session_id", [ANCESTOR, "not-a-session"], ids=["all succeeded", "unknown session"]
)
def test_a_session_that_failed_nothing_and_one_the_store_lacks_answer_empty(
    repository: FailureRepository, session_id: str
) -> None:
    """The same answer for both — no rows, nothing cut — which the page turns into its two
    404s by reading the header, not this."""
    answer = repository.failures(session_id=session_id, widths=ERRORS)
    assert answer == Failures(rows=[], cut=0, citation=answer.citation)


def test_a_store_nothing_was_extracted_into_answers_empty(tmp_path: Path) -> None:
    """A store with the schema and no sessions answers empty, and refuses nothing."""
    db = tmp_path / "traces.duckdb"
    StoreExporter(db, wait=NO_WAIT)
    with open_store(db, read_only=True, wait=NO_WAIT) as store:
        answer = store.failures.failures(session_id=FORK_ORIGIN, widths=ERRORS)
        assert answer == Failures(rows=[], cut=0, citation=answer.citation)


# --- refusals --------------------------------------------------------------------------------

# The one method, with one whole call, so a keyword can be dropped from it or added to it.
CALL: dict[str, Any] = {"session_id": FORK_ORIGIN, "widths": ERRORS}


def test_a_keyword_left_off_or_added_is_refused(repository: FailureRepository) -> None:
    """The method binds exactly what its statement declares, keyword by keyword: a drifted
    signature fails here before any page runs."""
    # Untyped, so the checker lets a call drift the way a page's could.
    method: Callable[..., Any] = repository.failures
    # The whole call runs...
    method(**CALL)
    # ...one keyword short, it does not...
    with pytest.raises(TypeError, match="missing"):
        method(**{key: value for key, value in CALL.items() if key != "widths"})
    # ...nor with one it never named...
    with pytest.raises(TypeError, match="unexpected keyword"):
        method(**CALL, source="main")
    # ...nor positionally: the keywords are the contract.
    with pytest.raises(TypeError, match="positional"):
        method(*CALL.values())


def test_a_surface_short_of_the_title_width_is_refused_by_the_binder(
    repository: FailureRepository,
) -> None:
    """The widths are held to the statement too, in the binder's own words."""
    short: dict[str, Any] = {**CALL, "widths": {}}
    with pytest.raises(ValueError, match="binds nav_chars"):
        repository.failures(**short)


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_every_failure_of_the_real_archive_builds_its_model(tmp_path: Path) -> None:
    """Every failed tool call of every session, over the archive on this machine, under the
    strict build, at a cap the archive's busiest session fits under.

    Counts only: a tool's fields are session content, and a failing assertion prints its
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
        sessions = rows_of(
            store,
            "SELECT session_id, count(*) AS failed FROM live_tool_calls WHERE is_error"
            " GROUP BY ALL",
            {},
        )
        assert sessions, "the archive holds no failure, so this leaf proved nothing"
        built = 0
        for one in sessions:
            answer = store.failures.failures(
                session_id=one["session_id"], widths={**ERRORS, "errors": one["failed"]}
            )
            assert (len(answer.rows), answer.cut) == (one["failed"], 0)
            built += len(answer.rows)
    assert built == sum(one["failed"] for one in sessions)
