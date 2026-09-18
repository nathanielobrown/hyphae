"""The `Store` handle: the one verb its repositories run SQL through, and the door that hands
one out.

Locking is not this file's business — `test_trace_store__locking.py` covers both waits,
`StoreLocked`, and a refused store freeing its lock. What is pinned here is the shape `_rows`
answers with, that a missing binding is refused rather than bound NULL, that the macros are
installed and DDL runs (the repositories' DDL and every `view_*` cut go through this verb),
that `open_store` raises what the door under it raises, and that `read_only` reaches the door.

The ratchet at the end is the store's boundary: which modules outside the package reach
`_rows`, `_connection`, the enrichment repository's `connection`, or the library's `fetch` and
`one` — none. The underscore is the package line, and `SLF001` holds the same door at the hook
(`pyproject.toml`); this leaf holds it at test tier, and sees the two public doors the lint
cannot: the delegate, and the library's pair, public so a repository module can call them.
"""

import ast
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from functools import cached_property
from pathlib import Path
from typing import NamedTuple

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
# The handle's two private verbs, the one public name that re-spells one of them
# (`store.enrichment.connection`, the planter's door to the driver), the library's two SQL
# doors over `_rows` (public so a repository module can call them), and the modules outside
# the store reaching any of them: none. The public names of a handle are its repositories.
VERBS = frozenset({"_rows", "_connection"})
DELEGATE = "connection"
LIBRARY = "hyphae.store.library"
DOORS = frozenset({"fetch", "one"})
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
        fetched = store._rows(
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
            store._rows(statement, {})
        # ...and with the id supplied the same statement answers one row.
        assert store._rows(statement, {"session_id": SPINE}).rows == [(SPINE,)]


def test_open_store_installs_the_macros_and_rows_runs_ddl(corpus_db: Path) -> None:
    """What the repositories' DDL and every `view_*` cut need from the one verb."""
    with open_store(corpus_db, read_only=True, wait=NO_WAIT) as store:
        # If a statement calls a library macro by name, the handle has installed it: `cut`
        # takes one character past the width so a page can mark the stop.
        assert store._rows("SELECT cut('abcdef', 3) AS shown", {}) == Fetched(
            ("shown",), [("abcd",)]
        )
        # ...and a temp-table DDL runs through the same verb and answers a `Fetched`...
        built = store._rows(
            "CREATE OR REPLACE TEMP TABLE probe AS SELECT id AS session_id FROM sessions"
            " WHERE id = $id",
            {"id": SPINE},
        )
        assert isinstance(built, Fetched)
        # ...after which the table it built is readable on the same handle.
        assert store._rows("SELECT session_id FROM probe", {}) == Fetched(
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
        writer._rows("CREATE TABLE probe (n INTEGER)", {})
    # ...and a read-only open of the same file refuses the same statement, naming the mode.
    with open_store(mutable_db, read_only=True, wait=NO_WAIT) as reader:
        with pytest.raises(duckdb.Error, match="read-only"):
            reader._rows("CREATE TABLE probe_again (n INTEGER)", {})
        # The write above did land: this is the same file, a different mode.
        assert reader._rows("SELECT count(*) FROM probe", {}).rows == [(0,)]


def test_wait_reaches_the_door(mutable_db: Path) -> None:
    """A store held briefly by a writer is read once the writer lets go, inside the wait given."""
    # If another process holds the write lock for a moment, an open with a budget past the
    # hold queues behind it rather than refusing...
    with (
        locked(mutable_db, hold=BRIEF_HOLD),
        open_store(mutable_db, read_only=True, wait=LOCK_TIMEOUT) as store,
    ):
        (row,) = store._rows("SELECT count(*) FROM sessions", {}).rows
    # ...and reads the store the writer let go of.
    assert row[0] > 0


def outside_the_store() -> list[tuple[str, ast.Module]]:
    """Every module under the package but the store's, parsed, keyed by its path in the package."""
    return [
        (str(path.relative_to(PACKAGE)), ast.parse(path.read_text(), filename=str(path)))
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.relative_to(PACKAGE).parts[0] != "store"
    ]


def reached(modules: list[tuple[str, ast.Module]]) -> set[str]:
    """The modules among `modules` reading `._rows` or `._connection` off something spelled
    `store`, `.connection` off `store.enrichment`, or the library's `fetch` or `one` by any name
    the module imports them under.

    Keyed on the receiver's spelling rather than its type, because every handle outside the store
    is named `store` (the leaf below holds that), and a type-keyed scan cannot see what
    `enter_context(open_store(...))` binds. The receiver is the bare name or an attribute by it —
    `self.store._rows`, the shape of an object that stashed the handle, as `walk.py`'s reader does.
    An answer's `rows` (`models/listing.py:Answer`) is another name on another receiver, so a
    page reading a repository's answer never lands here. The library's doors are keyed on the
    import instead, since `library` is a name a page imports for `bind` and `load` too.
    """
    return {module for module, tree in modules if reaches(tree)}


class LibraryNames(NamedTuple):
    """What one module binds from `hyphae.store.library`."""

    # Names bound to the module itself: `library` or an `as` alias.
    modules: frozenset[str]
    # Names bound to `fetch` or `one` directly, `as` alias included.
    doors: frozenset[str]


def library_names(tree: ast.Module) -> LibraryNames:
    """The names a module imports the library, or one of its doors, under."""
    modules: set[str] = set()
    doors: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "hyphae.store":
            modules.update(
                alias.asname or alias.name for alias in node.names if alias.name == "library"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == LIBRARY:
            doors.update(alias.asname or alias.name for alias in node.names if alias.name in DOORS)
        elif isinstance(node, ast.Import):
            modules.update(
                alias.asname or alias.name for alias in node.names if alias.name == LIBRARY
            )
    return LibraryNames(frozenset(modules), frozenset(doors))


def reaches(tree: ast.Module) -> bool:
    """Whether one module reaches the handle by any of the spellings `reached` names."""
    bound = library_names(tree)
    if bound.doors:
        return True
    return any(reaches_in(node, bound.modules) for node in ast.walk(tree))


def reaches_in(node: ast.AST, library: frozenset[str]) -> bool:
    """Whether one expression is `<store>._rows`, `<store>._connection`,
    `<store>.enrichment.connection`, or `.fetch` / `.one` off a name in `library`."""
    if not isinstance(node, ast.Attribute):
        return False
    if node.attr in VERBS:
        return spells_store(node.value)
    if node.attr in DOORS:
        return spells_library(node.value, library)
    return node.attr == DELEGATE and spells_enrichment(node.value)


def spells_store(receiver: ast.expr) -> bool:
    """Whether an expression is `store` or ends in `.store`."""
    return (isinstance(receiver, ast.Name) and receiver.id == "store") or (
        isinstance(receiver, ast.Attribute) and receiver.attr == "store"
    )


def spells_enrichment(receiver: ast.expr) -> bool:
    """Whether an expression is `<store>.enrichment`, the repository that delegates `connection`."""
    return (
        isinstance(receiver, ast.Attribute)
        and receiver.attr == "enrichment"
        and spells_store(receiver.value)
    )


def spells_library(receiver: ast.expr, library: frozenset[str]) -> bool:
    """Whether an expression is the library module: a name it was imported under, or the
    dotted path a bare `import hyphae.store.library` leaves it at."""
    return (isinstance(receiver, ast.Name) and receiver.id in library) or (
        isinstance(receiver, ast.Attribute) and ast.unparse(receiver) == LIBRARY
    )


def handles_named(modules: list[tuple[str, ast.Module]]) -> set[str]:
    """Every name a handle is held under in `modules`: parameters annotated as one, `with`
    targets and `enter_context` assignments of `open_store`, and whatever one of those is then
    assigned to, `db = store`, `db: Store = store` or `self.db = store`."""
    names: set[str] = set()
    trees = [tree for _, tree in modules]
    for tree in trees:
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
    # A second pass, since a walk reaches a body's assignment before the parameter it copies.
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign | ast.AnnAssign) and (
                isinstance(node.value, ast.Name) and node.value.id in names
            ):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names.update(rebound(target) for target in targets)
    return names


def rebound(target: ast.expr) -> str:
    """The name a plain assignment binds: the bare name, or the attribute of a stash."""
    return target.attr if isinstance(target, ast.Attribute) else ast.unparse(target)


def opens_a_store(expression: ast.expr) -> bool:
    return (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "open_store"
    )


# What the scan sees, one module each: the three handle spellings and the library's doors
# under every import shape are a reach; a repository's answer, another attribute of the
# enrichment repository, a handle under another name, and the library's other names are not.
SPELLINGS = [
    pytest.param("store._rows(sql, {})", True, id="verb"),
    pytest.param("self.store._connection.execute(sql)", True, id="verb_on_a_stash"),
    pytest.param("store.enrichment.connection.execute(sql)", True, id="delegate"),
    pytest.param(
        "from hyphae.store import library\nlibrary.fetch(store, sql, {})", True, id="door"
    ),
    pytest.param(
        "from hyphae.store import library as lib\nlib.one(store, name, {})", True, id="door_alias"
    ),
    pytest.param("from hyphae.store.library import one", True, id="door_by_name"),
    pytest.param(
        "import hyphae.store.library\nhyphae.store.library.fetch(store, sql, {})",
        True,
        id="door_dotted",
    ),
    pytest.param("answer.rows", False, id="an_answers_rows"),
    pytest.param("store.enrichment.held(item)", False, id="a_repository_method"),
    pytest.param("db._rows(sql, {})", False, id="a_handle_under_another_name"),
    pytest.param(
        "from hyphae.store import library\nlibrary.load(name)", False, id="the_library_itself"
    ),
    pytest.param("reading.fetch(sql)", False, id="fetch_on_something_else"),
]


@pytest.mark.parametrize(("source", "reaching"), SPELLINGS)
def test_the_scan_sees_each_spelling_of_a_reach_and_nothing_beside_it(
    source: str, *, reaching: bool
) -> None:
    """Every spelling the ratchet refuses is seen in a module of one line, and the names that
    merely look like one are not."""
    assert reached([("plant.py", ast.parse(source))]) == ({"plant.py"} if reaching else set())


@pytest.mark.reads_the_repo  # reads every module outside the store package
def test_no_module_outside_the_store_reaches_the_handle() -> None:
    """The ratchet: `_rows`, `_connection`, the enrichment repository's `connection` and the
    library's `fetch` and `one` are the store's, and no module outside borrows them.

    `==` rather than `<=`, so a module that stops reaching in is a red here as well as a new one
    that starts — the set is a fact the PR that changes it states.
    """
    assert reached(outside_the_store()) == REACHING


@pytest.mark.reads_the_repo  # reads every module outside the store package
def test_every_store_handle_outside_the_store_is_named_store() -> None:
    """The spelling the ratchet keys on: a handle outside the store is always `store`.

    A parameter typed `Store` or `Db` under another name, `open_store` opened `as db`, or a
    `store` copied into `db`, would be a handle the scan above cannot see reaching in.
    """
    assert handles_named(outside_the_store()) == {"store"}


# What the handle scan sees, one module each: each way a handle arrives, and each way one is
# copied to another name afterwards, whichever order the two are written in.
HELD = [
    pytest.param("def f(store: Store): ...", {"store"}, id="parameter"),
    pytest.param("def f(store: Store | None): ...", {"store"}, id="optional_parameter"),
    pytest.param("with open_store(path) as db: ...", {"db"}, id="with_target"),
    pytest.param("db = stack.enter_context(open_store(path))", {"db"}, id="entered"),
    pytest.param("def f(store: Store):\n    db = store", {"store", "db"}, id="copied"),
    pytest.param("def f(store: Store):\n    db: Store = store", {"store", "db"}, id="copied_typed"),
    pytest.param("def f(store: Store):\n    self.db = store", {"store", "db"}, id="stashed"),
    pytest.param("db = store\ndef f(store: Store): ...", {"store", "db"}, id="copied_above"),
    pytest.param("def f(store: Store):\n    db = other", {"store"}, id="copied_from_elsewhere"),
]


@pytest.mark.parametrize(("source", "held"), HELD)
def test_the_scan_sees_each_name_a_handle_is_held_under(source: str, held: set[str]) -> None:
    """Every way a module takes a handle or copies it to another name is seen, in a module of
    one or two lines, and a copy of something else is not."""
    assert handles_named([("plant.py", ast.parse(source))]) == held


@pytest.mark.reads_the_repo  # reads the class namespace, which mutmut fills with `xǁ` variants
def test_the_public_names_of_a_handle_are_its_repositories() -> None:
    """What `Store` exports is one property per repository and nothing else — no public alias
    of a verb the ratchet and the lint watch by their private names."""
    # The class namespace holds one public name per repository...
    public = {name for name in vars(Store) if not name.startswith("_")}
    repositories = {
        name for name, member in vars(Store).items() if isinstance(member, cached_property)
    }
    assert public == repositories
    assert "sessions" in repositories
    # ...and a fresh handle holds no public name of its own: an alias `__init__` sets, which the
    # class namespace never shows, would be the one public name on it before any repository is
    # read, since a `cached_property` writes into the instance only once read.
    assert not {name for name in vars(Store(duckdb.connect())) if not name.startswith("_")}
