"""The `Store` handle: the one verb every layer above the store runs SQL through, and the door
that hands one out.

Locking is not this file's business — `test_trace_store__locking.py` covers both waits,
`StoreLocked`, and a refused store freeing its lock. What is pinned here is the shape `rows`
answers with, that a missing binding is refused rather than bound NULL, that the macros are
installed and DDL runs (the repositories' DDL and every `view_*` cut go through this verb),
that `open_store` raises what the door under it raises, and that `read_only` reaches the door.

The ratchet at the end is the store's boundary: which modules outside the package run SQL
through `rows` or read `connection` — none, now that phase 4 has moved each behind a
repository; phase 5 makes both private (`plans/store-layering/phase-4-repositories.md`).
"""

import ast
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import duckdb
import pytest

import hyphae
from hyphae.store.handle import Fetched, Store, open_store
from hyphae.store.schema import SCHEMA_VERSION, SchemaVersionError
from hyphae.store.trace_store import StoreLocked, open_trace_store
from tests.conftest import LOCK_TIMEOUT, NO_WAIT, RESUME, SPINE, locked

# The two corpus sessions the leaves below name, in the order `ORDER BY id` puts them.
NAMED = sorted((RESUME, SPINE))
# How long the lock holder below keeps the store before letting go on its own.
BRIEF_HOLD = 0.4

PACKAGE = Path(hyphae.__file__).parent
# The two verbs the handle exposes, and the modules outside the store still reaching them: none.
# Each repository PR proved its module left with a leaf of its own (`tests/store/test_analysis.py`
# for the runner, `tests/store/test_enrichment__reads.py` for the viewer's enrichment reads);
# phase 5 makes the verbs private and pins the handle's public names to the repositories.
VERBS = frozenset({"rows", "connection"})
REACHING: frozenset[str] = frozenset()
# How a handle is spelled outside the store: an annotation of the handle or the viewer's
# dependency alias, or the target `open_store` is opened into.
HANDLE = frozenset({"Store", "Db"})


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
    """What the repositories' DDL and every `view_*` cut need from the one verb."""
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


def outside_the_store() -> list[tuple[str, ast.Module]]:
    """Every module under the package but the store's, parsed, keyed by its path in the package."""
    return [
        (str(path.relative_to(PACKAGE)), ast.parse(path.read_text(), filename=str(path)))
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.relative_to(PACKAGE).parts[0] != "store"
    ]


def reached() -> set[str]:
    """The modules outside the store reading `.rows` or `.connection` off something spelled `store`.

    Keyed on the receiver's spelling rather than its type, because every handle outside the store
    is named `store` (the leaf below holds that), and a type-keyed scan cannot see what
    `enter_context(open_store(...))` binds. The receiver is the bare name or an attribute by it —
    `self.store.rows`, the shape of an object that stashed the handle, as `walk.py`'s reader does.
    An answer's `rows` (`models/listing.py:Answer`) sits on another receiver, so a page
    reading a repository's answer never lands here.
    """
    return {
        module
        for module, tree in outside_the_store()
        if any(
            isinstance(node, ast.Attribute) and node.attr in VERBS and spells_store(node.value)
            for node in ast.walk(tree)
        )
    }


def spells_store(receiver: ast.expr) -> bool:
    """Whether an expression is `store` or ends in `.store`."""
    return (isinstance(receiver, ast.Name) and receiver.id == "store") or (
        isinstance(receiver, ast.Attribute) and receiver.attr == "store"
    )


def handles_named() -> set[str]:
    """Every name a handle is held under outside the store: parameters annotated as one, `with`
    targets and `enter_context` assignments of `open_store`."""
    names: set[str] = set()
    for _, tree in outside_the_store():
        for node in ast.walk(tree):
            if isinstance(node, ast.arg) and node.annotation is not None:
                spelled = ast.unparse(node.annotation)
                if spelled in HANDLE or spelled.removesuffix(" | None") in HANDLE:
                    names.add(node.arg)
            elif isinstance(node, ast.withitem) and opens_a_store(node.context_expr):
                if node.optional_vars is not None:
                    names.add(ast.unparse(node.optional_vars))
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                entered = node.value.func
                if (
                    isinstance(entered, ast.Attribute)
                    and entered.attr == "enter_context"
                    and any(opens_a_store(argument) for argument in node.value.args)
                ):
                    names.update(ast.unparse(target) for target in node.targets)
    return names


def opens_a_store(expression: ast.expr) -> bool:
    return (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "open_store"
    )


@pytest.mark.reads_the_repo  # reads every module outside the store package
def test_no_module_outside_the_store_reaches_the_handle() -> None:
    """The ratchet: `rows` and `connection` are the store's, and no module outside borrows them.

    `==` rather than `<=`, so a module that stops reaching in is a red here as well as a new one
    that starts — the set is a fact the PR that changes it states.
    """
    assert reached() == REACHING


@pytest.mark.reads_the_repo  # reads every module outside the store package
def test_every_store_handle_outside_the_store_is_named_store() -> None:
    """The spelling the ratchet keys on: a handle outside the store is always `store`.

    A parameter typed `Store` or `Db` under another name, or `open_store` opened `as db`, would be
    a handle the scan above cannot see reaching in.
    """
    assert handles_named() == {"store"}
