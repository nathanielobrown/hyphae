"""The `Store` handle: the one verb every layer above the store runs SQL through, and the door
that hands one out.

Locking is not this file's business — `test_trace_store__locking.py` covers both waits,
`StoreLocked`, and a refused store freeing its lock. What is pinned here is the shape `rows`
answers with, that a missing binding is refused rather than bound NULL, that the macros are
installed and DDL runs (the runner's relations and every `view_*` cut go through this verb),
that `open_store` raises what the door under it raises, and that `read_only` reaches the door.
"""

from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import duckdb
import pytest

from hyphae.store.handle import Fetched, Store, open_store
from hyphae.store.schema import SCHEMA_VERSION, SchemaVersionError
from hyphae.store.trace_store import StoreLocked, open_trace_store
from tests.conftest import LOCK_TIMEOUT, NO_WAIT, RESUME, SPINE, locked

# The two corpus sessions the leaves below name, in the order `ORDER BY id` puts them.
NAMED = sorted((RESUME, SPINE))
# How long the lock holder below keeps the store before letting go on its own.
BRIEF_HOLD = 0.4


def test_rows_answers_the_columns_the_statement_named_and_the_rows_as_tuples(
    corpus_db: Path,
) -> None:
    """One `Fetched`: column names in statement order, then the rows, bound by name."""
    with open_trace_store(corpus_db, read_only=True, wait=NO_WAIT) as connection:
        store = Store(connection)
        # If a statement names two columns and binds two ids...
        fetched = store.rows(
            "SELECT id, id = $spine AS is_spine FROM sessions"
            " WHERE id IN ($spine, $resume) ORDER BY id",
            {"spine": SPINE, "resume": RESUME},
        )
    # ...then the answer is compared whole: the names as the statement spelt them, the rows
    # as tuples in the statement's order, and nothing else on it.
    assert fetched == Fetched(
        ("id", "is_spine"), [(session_id, session_id == SPINE) for session_id in NAMED]
    )


def test_rows_refuses_a_binding_the_statement_names_and_the_caller_left_out(
    corpus_db: Path,
) -> None:
    """A parameter with no value is the driver's own error, not a NULL bound in its place."""
    with open_trace_store(corpus_db, read_only=True, wait=NO_WAIT) as connection:
        store = Store(connection)
        statement = "SELECT id FROM sessions WHERE id = $session_id"
        # If the statement binds `$session_id` and the caller supplies nothing...
        with pytest.raises(duckdb.Error, match="session_id"):
            store.rows(statement, {})
        # ...and with the id supplied the same statement answers one row.
        assert store.rows(statement, {"session_id": SPINE}).rows == [(SPINE,)]


def test_open_store_installs_the_macros_and_rows_runs_ddl(corpus_db: Path) -> None:
    """What the runner's relations and every `view_*` cut need from the one verb."""
    with open_store(corpus_db, read_only=True, wait=NO_WAIT) as store:
        # If a statement calls a library macro by name, the handle has installed it: `cut`
        # takes one character past the width so a page can mark the stop.
        assert store.rows("SELECT cut('abcdef', 3) AS shown", {}) == Fetched(
            ("shown",), [("abcd",)]
        )
        # ...and a temp-table DDL runs through the same verb and answers a `Fetched`...
        built = store.rows(
            "CREATE OR REPLACE TEMP TABLE probe AS SELECT id AS session_id FROM sessions"
            " WHERE id = $id",
            {"id": SPINE},
        )
        assert isinstance(built, Fetched)
        # ...after which the table it built is readable on the same handle.
        assert store.rows("SELECT session_id FROM probe", {}) == Fetched(
            ("session_id",), [(SPINE,)]
        )


@contextmanager
def gone(path: Path) -> Generator[None]:
    """The file removed: a typo in `--db` from the door's point of view."""
    path.unlink()
    yield


@contextmanager
def bumped(path: Path) -> Generator[None]:
    """A store another schema version wrote, which a read-only open cannot migrate."""
    with duckdb.connect(str(path)) as connection:
        connection.execute("UPDATE meta SET schema_version = ?", [SCHEMA_VERSION - 1])
    yield


@contextmanager
def held(path: Path) -> Generator[None]:
    """Another process holding the write lock for the whole block."""
    with locked(path):
        yield


@pytest.mark.parametrize(
    ("spoil", "refusal"),
    [(gone, FileNotFoundError), (bumped, SchemaVersionError), (held, StoreLocked)],
    ids=["missing", "other_schema", "locked"],
)
def test_open_store_raises_what_the_door_raises(
    mutable_db: Path,
    spoil: Callable[[Path], AbstractContextManager[None]],
    refusal: type[Exception],
) -> None:
    """Nothing is wrapped or renamed on the way out: a caller catches the door's own classes."""
    with (
        spoil(mutable_db),
        pytest.raises(refusal),
        open_store(mutable_db, read_only=True, wait=NO_WAIT),
    ):
        pass


def test_read_only_reaches_the_door(mutable_db: Path) -> None:
    """A write open can add a base table; a read-only one over the same file cannot."""
    # If the store is opened for write, a base table can be created...
    with open_store(mutable_db, read_only=False, wait=NO_WAIT) as writer:
        writer.rows("CREATE TABLE probe (n INTEGER)", {})
    # ...and a read-only open of the same file refuses the same statement, naming the mode.
    with open_store(mutable_db, read_only=True, wait=NO_WAIT) as reader:
        with pytest.raises(duckdb.Error, match="read-only"):
            reader.rows("CREATE TABLE probe_again (n INTEGER)", {})
        # The write above did land: this is the same file, a different mode.
        assert reader.rows("SELECT count(*) FROM probe", {}).rows == [(0,)]


def test_wait_reaches_the_door(mutable_db: Path) -> None:
    """A store held briefly by a writer is read once the writer lets go, inside the wait given."""
    # If another process holds the write lock for a moment, an open with a budget past the
    # hold queues behind it rather than refusing...
    with (
        locked(mutable_db, hold=BRIEF_HOLD),
        open_store(mutable_db, read_only=True, wait=LOCK_TIMEOUT) as store,
    ):
        (row,) = store.rows("SELECT count(*) FROM sessions", {}).rows
    # ...and reads the store the writer let go of.
    assert row[0] > 0
