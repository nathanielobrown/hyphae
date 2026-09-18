"""`NavRepository`: the NavTree's three levels and a session's runs, over the corpus store.

Each level is read whole at the NavTree's widths as the row model that keys it, a bucket and
a turn's tools are the same levels keyed NULL, a session's runs come back with where each
hangs, the methods bind exactly what their statements declare, and the table that keys the
levels names nothing but a NavTree row. The `HYPHAE_LIVE_STORE` leaf at the end is the
backstop over real shapes, off by default.
"""

import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation, ParamValue
from hyphae.models.nav import NavCallRow, NavToolRow, NavTurnRow, RunRow
from hyphae.store import library, nav
from hyphae.store.handle import Store, open_store
from hyphae.store.nav import NavRepository
from hyphae.view import bounds
from tests.conftest import (
    COMPACTED,
    DENSE_CALL,
    FORK_ORIGIN,
    FORK_ORIGIN_RUN,
    MAIN,
    NO_WAIT,
    SPINE,
    SPINE_RUN,
    THREE_BAND_TURN,
)
from tests.store.test_nodes import LOG, SPINE_MAIN
from tests.store.test_sessions import LIVE_STORE, rows_of

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")

# The one surface a level is drawn at, as the mapping the NavTree passes.
NAV = bounds.NAV_TREE_WIDTHS._asdict()
# One node at each level, by the keys its statement binds: the spine's main thread, its
# three-band turn, and the fork origin's dense call.
TURN_LEVEL: dict[str, ParamValue] = {**SPINE_MAIN}
CALL_LEVEL: dict[str, ParamValue] = {**SPINE_MAIN, "turn_id": THREE_BAND_TURN}
TOOL_LEVEL: dict[str, ParamValue] = {
    "session_id": FORK_ORIGIN,
    "source": FORK_ORIGIN_RUN,
    "api_call_id": DENSE_CALL,
    "turn_id": None,
}
# Every level, the statement that reads it, and the order its bindings quote in. Spelled
# here rather than read off `nav.LEVELS`, so two entries swapped are two reds here.
LEVELS: list[tuple[type[NavTurnRow | NavCallRow | NavToolRow], dict[str, ParamValue], str]] = [
    (NavTurnRow, TURN_LEVEL, "view_nav_tree_turns"),
    (NavCallRow, CALL_LEVEL, "view_nav_tree_calls"),
    (NavToolRow, TOOL_LEVEL, "view_nav_tree_tools"),
]


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> NavRepository:
    return store.nav


# --- the three levels --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "keys", "statement"), LEVELS, ids=[m.__name__ for m, _, _ in LEVELS]
)
def test_each_level_is_read_whole_as_the_model_that_keys_it(
    store: Store,
    repository: NavRepository,
    model: type[NavTurnRow | NavCallRow | NavToolRow],
    keys: dict[str, ParamValue],
    statement: str,
) -> None:
    """A level is every row its statement answers at the keys, in the statement's order and at
    the NavTree's widths, each as the model that keyed the read, beside the statement's citation."""
    answer = repository.level(model, keys, widths=NAV)
    bindings = library.bind(statement, NAV, {}, **keys)
    assert [asdict(row) for row in answer.rows] == rows_of(store, library.load(statement), bindings)
    assert answer.rows, f"{statement} answered nothing at {keys}, so the model was never built"
    assert all(isinstance(row, model) for row in answer.rows)
    assert answer.citation == Citation(statement, bindings)
    assert list(bindings) == [*keys, "nav_chars"]


def test_a_thread_bucket_and_a_turns_tools_are_the_same_levels_keyed_null(
    repository: NavRepository,
) -> None:
    """At `turn_id` NULL the calls level is a thread's unattributed bucket — the compacted
    session's main thread holds four — and at `api_call_id` NULL the tools level is every tool
    call under one turn, which the agents-only preset hangs straight off it."""
    bucket = repository.level(
        NavCallRow, {**SPINE_MAIN, "session_id": COMPACTED, "turn_id": None}, widths=NAV
    )
    assert len(bucket.rows) == 4
    assert bucket.citation.bindings["turn_id"] is None
    under_turn = repository.level(NavToolRow, {**CALL_LEVEL, "api_call_id": None}, widths=NAV)
    calls = repository.level(NavCallRow, CALL_LEVEL, widths=NAV)
    assert {row.call_index for row in under_turn.rows} <= {row.call_index for row in calls.rows}
    assert len(under_turn.rows) == sum(len(row.tools["names"] or []) for row in calls.rows)


def test_every_level_is_keyed_by_a_nav_row_model() -> None:
    """`LEVELS` names, per NavTree row model, the statement that reads its level, and nothing
    but a NavTree row keys it."""
    assert set(nav.LEVELS) == {NavTurnRow, NavCallRow, NavToolRow}
    assert all(statement.startswith("view_nav_tree_") for statement in nav.LEVELS.values())


# --- a session's runs --------------------------------------------------------------------------


def test_a_sessions_runs_are_read_whole_with_where_each_hangs(
    store: Store, repository: NavRepository
) -> None:
    """Every agent run of a session, in the order they started, at the widths of the surface
    reading them: the spine holds two, one spawned from a call of the main thread and one from
    a call of that run's own thread; the fork origin's two no tool call spawned, so their three
    `spawn_*` members are NULL together — which is the whole definition of unattached."""
    answer = repository.runs(session_id=SPINE, widths=NAV)
    bindings = library.bind("view_runs", NAV, {}, session_id=SPINE)
    assert [asdict(row) for row in answer.rows] == rows_of(
        store, library.load("view_runs"), bindings
    )
    assert len(answer.rows) == 2
    assert all(isinstance(row, RunRow) for row in answer.rows)
    assert [row.spawn_source for row in answer.rows] == [MAIN, SPINE_RUN]
    assert [row.run_id for row in answer.rows] == [SPINE_RUN, answer.rows[1].run_id]
    assert all(row.spawn_turn_id and row.spawn_call_id for row in answer.rows)
    assert answer.citation == Citation("view_runs", bindings)
    assert list(bindings) == ["session_id", "chip_chars"]
    unattached = repository.runs(session_id=FORK_ORIGIN, widths=NAV)
    assert [row.run_id for row in unattached.rows] == [FORK_ORIGIN_RUN, unattached.rows[1].run_id]
    assert {
        (row.spawn_source, row.spawn_turn_id, row.spawn_call_id) for row in unattached.rows
    } == {(None, None, None)}
    # The children log reads the same runs at its own widths; the surface is the caller's.
    logged = repository.runs(session_id=FORK_ORIGIN, widths=LOG)
    assert logged.citation.bindings["chip_chars"] == LOG["chip_chars"] != NAV["chip_chars"]


# --- refusals --------------------------------------------------------------------------------


def test_a_keyword_left_off_or_added_is_refused(repository: NavRepository) -> None:
    """Each method binds exactly what its statements declare: the widths are keyword-only,
    and the keys ride as one mapping rather than as keywords of their own."""
    level: Callable[..., Any] = repository.level
    level(NavTurnRow, TURN_LEVEL, widths=NAV)
    with pytest.raises(TypeError, match="missing"):
        level(NavTurnRow, TURN_LEVEL)
    with pytest.raises(TypeError, match="unexpected keyword"):
        level(NavTurnRow, TURN_LEVEL, widths=NAV, sizes={})
    with pytest.raises(TypeError, match="positional"):
        level(NavTurnRow, TURN_LEVEL, NAV)
    runs: Callable[..., Any] = repository.runs
    with pytest.raises(TypeError, match="positional"):
        runs(FORK_ORIGIN, NAV)
    with pytest.raises(TypeError, match="unexpected keyword"):
        runs(session_id=FORK_ORIGIN, widths=NAV, source=MAIN)


def test_a_key_or_a_width_the_statement_lacks_is_refused_by_the_binder(
    repository: NavRepository,
) -> None:
    """The keys and the widths are held to the statement, in the binder's own words: a key
    the statement never named, a key it needs, and a width short of what it binds."""
    with pytest.raises(ValueError, match="binds no api_call_id"):
        repository.level(NavCallRow, TOOL_LEVEL, widths=NAV)
    with pytest.raises(ValueError, match="binds turn_id"):
        repository.level(NavCallRow, TURN_LEVEL, widths=NAV)
    with pytest.raises(ValueError, match="binds nav_chars"):
        repository.level(NavTurnRow, TURN_LEVEL, widths={})
    with pytest.raises(ValueError, match="binds chip_chars"):
        repository.runs(session_id=FORK_ORIGIN, widths={})


def test_every_read_binds_through_the_binder(
    repository: NavRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every read goes through `library.bind`, so the binder holds each call to its statement
    — DuckDB refuses a key short or over too, but only once a connection is open, and its
    message names neither the statement nor the half at fault."""
    seen: list[str] = []
    bind = library.bind

    def watched(name: str, *parts: Any, **keys: ParamValue) -> dict[str, ParamValue]:
        seen.append(name)
        return bind(name, *parts, **keys)

    monkeypatch.setattr(library, "bind", watched)
    for model, keys, _ in LEVELS:
        repository.level(model, keys, widths=NAV)
    repository.runs(session_id=FORK_ORIGIN, widths=NAV)
    assert seen == [
        "view_nav_tree_turns",
        "view_nav_tree_calls",
        "view_nav_tree_tools",
        "view_runs",
    ]


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_every_level_and_run_of_the_real_archive_builds_its_model(tmp_path: Path) -> None:
    """A fixed sample of the archive's threads reads its turns level; of its turns, its calls
    level and the tools under the turn whole; of its api calls, its tools level; of its
    threads with calls answering no turn, the bucket's level; and of its sessions, their
    runs — every one as its model under the strict build. Sampled at 400 rows a shape, for
    the reason `tests/store/test_nodes__children.py`'s backstop gives.

    Counts only, and the archive copied first, for the reasons the header leaf gives.
    """
    archive = Path(os.environ[LIVE_STORE])
    copy = tmp_path / archive.name
    shutil.copy(archive, copy)
    wal = archive.with_name(f"{archive.name}.wal")
    if wal.exists():
        shutil.copy(wal, copy.with_name(f"{copy.name}.wal"))
    sample = "USING SAMPLE reservoir(400 ROWS) REPEATABLE (46)"
    counts: dict[str, int] = {}

    def count(name: str, rows: int) -> None:
        counts[name] = counts.get(name, 0) + rows

    with open_store(copy, read_only=True, wait=NO_WAIT) as store:
        threads = rows_of(
            store,
            f"SELECT * FROM (SELECT DISTINCT session_id, source FROM live_turns) {sample}",
            {},
        )
        assert threads, "the archive holds no turns, so this leaf proved nothing"
        for thread in threads:
            turns = store.nav.level(NavTurnRow, thread, widths=NAV)
            assert all(isinstance(row, NavTurnRow) for row in turns.rows)
            count("NavTurnRow", len(turns.rows))
        turns_sampled = rows_of(
            store, f"SELECT session_id, source, id AS turn_id FROM live_turns {sample}", {}
        )
        for keys in turns_sampled:
            calls = store.nav.level(NavCallRow, keys, widths=NAV)
            assert all(isinstance(row, NavCallRow) for row in calls.rows)
            count("NavCallRow", len(calls.rows))
            under = store.nav.level(NavToolRow, {**keys, "api_call_id": None}, widths=NAV)
            assert all(isinstance(row, NavToolRow) for row in under.rows)
            count("NavToolRow.turn", len(under.rows))
        calls_sampled = rows_of(
            store,
            f"SELECT session_id, source, id AS api_call_id, NULL AS turn_id"
            f" FROM live_api_calls {sample}",
            {},
        )
        for keys in calls_sampled:
            tools = store.nav.level(NavToolRow, keys, widths=NAV)
            assert all(isinstance(row, NavToolRow) for row in tools.rows)
            count("NavToolRow.call", len(tools.rows))
        buckets = rows_of(
            store,
            f"SELECT * FROM (SELECT DISTINCT session_id, source FROM live_api_calls"
            f" WHERE turn_id IS NULL) {sample}",
            {},
        )
        assert buckets, "the archive holds no unattributed api call, so the bucket arm ran dry"
        for thread in buckets:
            bucket = store.nav.level(NavCallRow, {**thread, "turn_id": None}, widths=NAV)
            assert bucket.rows, f"a thread with unattributed calls listed none: {thread}"
            count("NavCallRow.bucket", len(bucket.rows))
        for keys in rows_of(store, f"SELECT session_id FROM session_rollups {sample}", {}):
            runs = store.nav.runs(**keys, widths=NAV)
            assert all(isinstance(row, RunRow) for row in runs.rows)
            count("RunRow", len(runs.rows))
    print(f"\n{LIVE_STORE}: {counts}")  # noqa: T201 — the counts a person runs this for
