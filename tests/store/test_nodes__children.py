"""`NodeRepository`, past the header: a node's children, its numbers and its record.

Driven against the corpus store as `tests/store/test_nodes.py` is, whose constants this file
shares: a page of a node's children arrives with the level counted, a timeline page windowed
around the statement a report cites; a thread's compactions are read whole; a popover's
numbers and a turn's transcript line read as their models; the methods bind exactly what
their statements declare; and the table that keys the children names nothing a model lacks.
Split from the header file by topic, for the file budget.

The `HYPHAE_LIVE_STORE` leaf at the end is the backstop over real shapes, off by default.
"""

import dataclasses
import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation, ParamValue
from hyphae.models.node import CallRow, CompactionRow, TimelineRow, ToolRow, TurnRecord
from hyphae.models.record import WholeRecord
from hyphae.store import library, nodes
from hyphae.store.handle import Store, open_store
from hyphae.store.nodes import NodeRepository
from tests.conftest import (
    COMPACTED,
    COMPACTED_BOUNDARY,
    DENSE_CALL,
    DENSE_TOOL,
    FORK_ORIGIN,
    FORK_ORIGIN_RUN,
    MAIN,
    NO_WAIT,
    RESUME,
    SLASH_TURN,
    SPINE,
    THREE_BAND_TURN,
)
from tests.store.test_nodes import (
    CALL_KEYS,
    HEADER,
    LOG,
    PAGE,
    POPOVER,
    SPINE_MAIN,
    TURN_KEYS,
)
from tests.store.test_sessions import LIVE_STORE, rows_of
from tests.view.conftest import MISSING

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> NodeRepository:
    return store.nodes


# --- the children logs ------------------------------------------------------------------------

# A page of each shape a log lists: the four api calls under the spine's three-band turn, and
# the four tool calls the fork's dense call made. The statement and the name of its page size
# are spelled here rather than read off `nodes.CHILDREN`, for the reason `HELD` gives.
CHILDREN: list[tuple[type[CallRow | ToolRow], dict[str, str], str, str]] = [
    (CallRow, {**SPINE_MAIN, "turn_id": THREE_BAND_TURN}, "view_turn_calls", "page_calls"),
    (ToolRow, CALL_KEYS, "view_call_tools", "page_tools"),
]


@pytest.mark.parametrize(
    ("model", "keys", "statement", "page_size"), CHILDREN, ids=["calls", "tools"]
)
def test_a_page_of_children_reaches_its_model_with_the_level_counted(
    store: Store,
    repository: NodeRepository,
    model: type[CallRow | ToolRow],
    keys: dict[str, str],
    statement: str,
    page_size: str,
) -> None:
    """One numbered page of a level: the statement's own rows as strict models, with how many
    the level holds before its LIMIT bit, and the citation quoting the keys, then the page,
    then the width — the order the footer prints."""
    listed = repository.children(model, keys, skipped=1, size=2, widths=LOG)
    bindings = library.bind(statement, LOG, {}, **keys, skipped=1, **{page_size: 2})
    raw = rows_of(store, library.load(statement), bindings)
    assert [asdict(row) for row in listed.rows] == raw
    assert len(listed.rows) == 2
    assert listed.total == 4
    assert listed.citation == Citation(statement, bindings)
    assert list(bindings) == [*keys, "skipped", page_size, "log_chars"]


def test_a_thread_bucket_pages_the_calls_that_answer_no_turn(repository: NodeRepository) -> None:
    """At `turn_id` NULL the same read pages a thread's unattributed calls — the bucket's own
    children — and a page past the level is empty and counts nothing."""
    bucket: dict[str, ParamValue] = {"session_id": COMPACTED, "source": MAIN, "turn_id": None}
    unattributed = repository.children(CallRow, bucket, skipped=0, size=10, widths=LOG)
    assert len(unattributed.rows) == unattributed.total == 4
    assert unattributed.citation.bindings["turn_id"] is None
    beyond = repository.children(CallRow, bucket, skipped=10, size=10, widths=LOG)
    assert beyond.rows == []
    assert beyond.total == 0


def test_a_timeline_page_is_windowed_around_the_statement_a_report_cites(
    store: Store, repository: NodeRepository
) -> None:
    """`session_timeline` limits nothing itself, so the page is cut around it: the thread's
    turns in index order, each carrying the level's count, and the citation carrying the
    offset and the limit after the statement's own bindings."""
    page = repository.timeline(session_id=SPINE, skipped=1, size=2, widths=LOG)
    bindings = library.bind("session_timeline", LOG, {}, session_id=SPINE)
    raw = sorted(
        rows_of(store, library.load("session_timeline"), bindings),
        key=lambda row: row["turn_index"],
    )
    assert [asdict(row) for row in page.rows] == [{**row, "matched_rows": 4} for row in raw[1:3]]
    assert page.total == 4
    assert page.citation == Citation("session_timeline", {**bindings, "offset": 1, "limit": 2})
    assert list(page.citation.bindings) == ["session_id", "log_chars", "offset", "limit"]


def test_a_run_timeline_is_the_same_page_keyed_by_the_run(
    store: Store, repository: NodeRepository
) -> None:
    """An agent run's thread pages through `run_timeline`, bound by the run id its rows carry
    as their source; the fork origin's run holds one turn."""
    page = repository.run_timeline(
        session_id=FORK_ORIGIN, source=FORK_ORIGIN_RUN, skipped=0, size=10, widths=LOG
    )
    bindings = library.bind("run_timeline", LOG, {}, session_id=FORK_ORIGIN, source=FORK_ORIGIN_RUN)
    raw = rows_of(store, library.load("run_timeline"), bindings)
    assert [asdict(row) for row in page.rows] == [{**row, "matched_rows": 1} for row in raw]
    assert page.total == 1
    assert isinstance(page.rows[0], TimelineRow)
    assert page.citation == Citation("run_timeline", {**bindings, "offset": 0, "limit": 10})


def test_a_thread_that_only_holds_calls_no_turn_answers_pages_nothing(
    repository: NodeRepository,
) -> None:
    """A timeline's cursorless row — the calls that answer no turn — rides no page and is
    counted on none: `RESUME` answers turns that live in the session it resumed, so its own
    timeline is that row alone, and its pages are empty."""
    page = repository.timeline(session_id=RESUME, skipped=0, size=10, widths=LOG)
    assert page.rows == []
    assert page.total == 0


def test_a_threads_compactions_are_read_whole(store: Store, repository: NodeRepository) -> None:
    """A thread's compactions are every marker the statement answers, in order, at the widths
    of the surface reading them: the compacted session's main thread holds two, the boundary
    first, and the spine's holds none."""
    answer = repository.compactions(session_id=COMPACTED, source=MAIN, widths=HEADER)
    bindings = library.bind("view_compactions", HEADER, {}, session_id=COMPACTED, source=MAIN)
    raw = rows_of(store, library.load("view_compactions"), bindings)
    assert [asdict(row) for row in answer.rows] == raw
    assert len(answer.rows) == 2
    assert isinstance(answer.rows[0], CompactionRow)
    assert answer.rows[0].compaction_id == COMPACTED_BOUNDARY
    assert answer.citation == Citation("view_compactions", bindings)
    assert list(bindings) == ["session_id", "source", "chip_chars"]
    none = repository.compactions(session_id=SPINE, source=MAIN, widths=HEADER)
    assert none.rows == []


# --- the popovers -----------------------------------------------------------------------------

# One node of each kind made of api calls, as the popover keys it: the thread its window is
# read on, and its own id under the statement's one name for it.
MEASURED: list[tuple[str, str, str, str]] = [
    ("session", SPINE, MAIN, SPINE),
    ("run", FORK_ORIGIN, FORK_ORIGIN_RUN, FORK_ORIGIN_RUN),
    ("turn", SPINE, MAIN, THREE_BAND_TURN),
    ("call", FORK_ORIGIN, FORK_ORIGIN_RUN, DENSE_CALL),
]


@pytest.mark.parametrize(
    ("kind", "session_id", "source", "node_id"), MEASURED, ids=[k for k, *_ in MEASURED]
)
def test_a_nodes_numbers_reach_their_model_whole(
    store: Store, repository: NodeRepository, kind: str, session_id: str, source: str, node_id: str
) -> None:
    """The numbers behind a NavTree row are `view_numbers`'s one row as a strict model, the
    per-model token groups included, bound in the order the footer quotes: the keys, the kind,
    then the popover's width."""
    numbers = repository.numbers(
        kind=kind, session_id=session_id, source=source, node_id=node_id, widths=POPOVER
    )
    bindings = library.bind(
        "view_numbers",
        POPOVER,
        {},
        session_id=session_id,
        source=source,
        node_id=node_id,
        kind=kind,
    )
    (raw,) = rows_of(store, library.load("view_numbers"), bindings)
    row = asdict(numbers)
    assert row.pop("citation") == Citation("view_numbers", bindings)
    assert row == raw
    assert numbers.api_calls > 0
    assert numbers.spent[0]["input_tokens"] == raw["spent"][0]["input_tokens"]
    assert list(bindings) == ["session_id", "source", "node_id", "kind", "model_chars"]


def test_a_node_with_no_api_calls_under_it_is_a_reading_of_nothing(
    repository: NodeRepository,
) -> None:
    """The statement aggregates, so a node the store never held answers as readily as one it
    did: no model, no window, no calls, and nothing spent under it — which the popover prints
    as the dashes it is, rather than a 404."""
    nothing = repository.numbers(
        kind="turn", session_id=SPINE, source=MAIN, node_id=MISSING, widths=POPOVER
    )
    assert nothing.model is None
    assert nothing.window_tokens is None
    assert nothing.api_calls == 0
    assert nothing.subtree_usd == 0
    assert nothing.spent == []


def test_a_tool_calls_numbers_name_the_calls_asked_beside_it(
    repository: NodeRepository,
) -> None:
    """A tool call is measured in characters, with the tools asked in the same api call listed
    beside it: the dense call asked four, so its `Read` has three siblings and none cut; and a
    tool call the store never held has no numbers."""
    numbers = repository.tool_numbers(
        session_id=FORK_ORIGIN, source=FORK_ORIGIN_RUN, tool_call_id=DENSE_TOOL, widths=POPOVER
    )
    assert numbers is not None
    assert numbers.input_chars == 27
    assert numbers.result_chars == 10
    assert numbers.offload_file is None
    assert len(numbers.siblings) == 3
    assert numbers.siblings_cut == 0
    assert numbers.spawned_run is False
    assert numbers.citation == Citation(
        "view_numbers_tool",
        {
            "session_id": FORK_ORIGIN,
            "source": FORK_ORIGIN_RUN,
            "tool_call_id": DENSE_TOOL,
            "item_chars": POPOVER["item_chars"],
            "head_items": POPOVER["head_items"],
        },
    )
    assert (
        repository.tool_numbers(
            session_id=FORK_ORIGIN, source=FORK_ORIGIN_RUN, tool_call_id=MISSING, widths=POPOVER
        )
        is None
    )


def test_a_compactions_numbers_are_the_window_it_dropped(repository: NodeRepository) -> None:
    """A compaction is measured in the window it freed, both ends and the word recorded for
    why; one the store never held has no numbers."""
    numbers = repository.compaction_numbers(
        session_id=COMPACTED, source=MAIN, compaction_id=COMPACTED_BOUNDARY, widths=POPOVER
    )
    assert numbers is not None
    assert numbers.pre_tokens == 171313
    assert numbers.post_tokens == 9478
    assert numbers.freed == 161835
    assert numbers.trigger == "manual"
    assert numbers.citation == Citation(
        "view_numbers_compaction",
        {
            "session_id": COMPACTED,
            "source": MAIN,
            "compaction_id": COMPACTED_BOUNDARY,
            "chip_chars": POPOVER["chip_chars"],
        },
    )
    assert (
        repository.compaction_numbers(
            session_id=COMPACTED, source=MAIN, compaction_id=MISSING, widths=POPOVER
        )
        is None
    )


# --- the records behind a thread --------------------------------------------------------------


def test_every_turn_of_a_thread_names_the_line_it_was_read_from(
    store: Store, repository: NodeRepository
) -> None:
    """A thread's turns each join to one transcript line, read for the whole thread at once
    and cited by the thread's two keys alone."""
    answer = repository.turn_records(session_id=SPINE, source=MAIN)
    raw = rows_of(store, library.load("view_turn_records"), SPINE_MAIN)
    assert [asdict(row) for row in answer.rows] == raw
    assert len(answer.rows) == 4
    assert all(isinstance(row, TurnRecord) for row in answer.rows)
    assert answer.citation == Citation("view_turn_records", SPINE_MAIN)
    assert repository.turn_records(session_id=SPINE, source=MISSING).rows == []


def test_a_record_is_read_whole_at_its_line(store: Store, repository: NodeRepository) -> None:
    """One archived record comes back whole at the line the citation names — the spine's third
    line is its `mode` record, 87 characters that no width cut — and a line past the thread's
    last is None."""
    keyed = {**SPINE_MAIN, "line_no": 3}
    whole = repository.record(session_id=SPINE, source=MAIN, line_no=3)
    (raw,) = rows_of(store, library.load("view_record"), keyed)
    assert len(raw["raw"]) == 87
    assert whole == WholeRecord(
        line_no=3,
        uuid=None,
        type="mode",
        timestamp=None,
        raw_chars=87,
        raw=raw["raw"],
        citation=Citation("view_record", keyed),
    )
    assert repository.record(session_id=SPINE, source=MAIN, line_no=43) is None
    assert repository.record(session_id=SPINE, source=MAIN, line_no=0) is None


# --- the table ---------------------------------------------------------------------------------


def test_every_child_shape_is_keyed_by_a_counted_model() -> None:
    """`CHILDREN` names, per row model a log lists, the statement that pages it and what that
    statement calls its page size — and each model carries the count the page reads."""
    assert set(nodes.CHILDREN) == {CallRow, ToolRow}
    for model, (statement, page_size) in nodes.CHILDREN.items():
        assert "matched_rows" in {one.name for one in dataclasses.fields(model)}
        assert statement.startswith("view_")
        assert page_size.startswith("page_")


# --- refusals --------------------------------------------------------------------------------


def test_a_keyword_left_off_or_added_is_refused(repository: NodeRepository) -> None:
    """Each method binds exactly what its statements declare: the widths and the sizes are
    keyword-only, and the keys ride as one mapping rather than as keywords of their own."""
    children: Callable[..., Any] = repository.children
    children(CallRow, TURN_KEYS, skipped=0, size=1, widths=LOG)
    with pytest.raises(TypeError, match="missing"):
        children(CallRow, TURN_KEYS, skipped=0, size=1)
    with pytest.raises(TypeError, match="unexpected keyword"):
        children(CallRow, TURN_KEYS, skipped=0, size=1, widths=LOG, sizes=PAGE)
    with pytest.raises(TypeError, match="positional"):
        children(CallRow, TURN_KEYS, 0, 1, LOG)
    numbers: Callable[..., Any] = repository.numbers
    with pytest.raises(TypeError, match="positional"):
        numbers("turn", SPINE, MAIN, THREE_BAND_TURN, POPOVER)
    with pytest.raises(TypeError, match="unexpected keyword"):
        numbers(
            kind="turn",
            session_id=SPINE,
            source=MAIN,
            node_id=THREE_BAND_TURN,
            widths=POPOVER,
            sizes=PAGE,
        )


def test_a_key_or_a_width_the_statement_lacks_is_refused_by_the_binder(
    repository: NodeRepository,
) -> None:
    """The keys and the widths are held to the statement, in the binder's own words: a key
    the statement never named, and a width short of what it binds."""
    with pytest.raises(ValueError, match="binds no turn_id"):
        repository.children(ToolRow, TURN_KEYS, skipped=0, size=1, widths=LOG)
    with pytest.raises(ValueError, match="binds log_chars"):
        repository.children(CallRow, TURN_KEYS, skipped=0, size=1, widths={})
    with pytest.raises(ValueError, match="binds model_chars"):
        repository.numbers(
            kind="turn", session_id=SPINE, source=MAIN, node_id=SLASH_TURN, widths=LOG
        )


def test_every_read_binds_through_the_binder(
    repository: NodeRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read that prints at no width still goes through `library.bind`, so the binder holds
    every call to its statement — DuckDB refuses a key short or over too, but only once a
    connection is open, and its message names neither the statement nor the half at fault."""
    seen: list[str] = []
    bind = library.bind

    def watched(name: str, *parts: Any, **keys: ParamValue) -> dict[str, ParamValue]:
        seen.append(name)
        return bind(name, *parts, **keys)

    monkeypatch.setattr(library, "bind", watched)
    repository.children(CallRow, TURN_KEYS, skipped=0, size=1, widths=LOG)
    repository.children(ToolRow, CALL_KEYS, skipped=0, size=1, widths=LOG)
    repository.timeline(session_id=SPINE, skipped=0, size=1, widths=LOG)
    repository.run_timeline(
        session_id=FORK_ORIGIN, source=FORK_ORIGIN_RUN, skipped=0, size=1, widths=LOG
    )
    repository.compactions(session_id=COMPACTED, source=MAIN, widths=HEADER)
    repository.numbers(
        kind="turn", session_id=SPINE, source=MAIN, node_id=SLASH_TURN, widths=POPOVER
    )
    repository.tool_numbers(
        session_id=FORK_ORIGIN, source=FORK_ORIGIN_RUN, tool_call_id=DENSE_TOOL, widths=POPOVER
    )
    repository.compaction_numbers(
        session_id=COMPACTED, source=MAIN, compaction_id=COMPACTED_BOUNDARY, widths=POPOVER
    )
    repository.turn_records(session_id=SPINE, source=MAIN)
    repository.record(session_id=SPINE, source=MAIN, line_no=3)
    assert seen == [
        "view_turn_calls",
        "view_call_tools",
        "session_timeline",
        "run_timeline",
        "view_compactions",
        "view_numbers",
        "view_numbers_tool",
        "view_numbers_compaction",
        "view_turn_records",
        "view_record",
    ]


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_every_page_number_and_record_of_the_real_archive_builds_its_model(
    tmp_path: Path,
) -> None:
    """A fixed sample of the archive's threads reads its timeline's first page, its
    compactions and its turn records; of its turns, api calls and buckets, their first page
    of children and their numbers; of its runs, sessions, tool calls, compactions and
    records, their numbers or the record whole — every one as its model under the strict
    build.
    Sampled throughout, at 400 rows a shape: every read here is a query of its own, at
    3 to 15 ms apiece over the canonical archive, and the archive's five thousand threads
    alone outrun the suite's timeout.

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

    def count(name: str, rows: int = 1) -> None:
        counts[name] = counts.get(name, 0) + rows

    with open_store(copy, read_only=True, wait=NO_WAIT) as store:
        threads = rows_of(
            store,
            f"SELECT * FROM (SELECT DISTINCT session_id, source FROM live_turns) {sample}",
            {},
        )
        assert threads, "the archive holds no turns, so this leaf proved nothing"
        for thread in threads:
            if thread["source"] == MAIN:
                page = store.nodes.timeline(
                    session_id=thread["session_id"], skipped=0, size=50, widths=LOG
                )
            else:
                page = store.nodes.run_timeline(**thread, skipped=0, size=50, widths=LOG)
            assert all(isinstance(row, TimelineRow) for row in page.rows)
            count("TimelineRow", len(page.rows))
            marks = store.nodes.compactions(**thread, widths=HEADER)
            assert all(isinstance(row, CompactionRow) for row in marks.rows)
            count("CompactionRow", len(marks.rows))
            lines = store.nodes.turn_records(**thread)
            assert all(isinstance(row, TurnRecord) for row in lines.rows)
            count("TurnRecord", len(lines.rows))
        turns = rows_of(
            store, f"SELECT session_id, source, id AS turn_id FROM live_turns {sample}", {}
        )
        for keys in turns:
            calls = store.nodes.children(CallRow, keys, skipped=0, size=50, widths=LOG)
            assert all(isinstance(row, CallRow) for row in calls.rows)
            count("CallRow", len(calls.rows))
            turn_id = keys.pop("turn_id")
            store.nodes.numbers(kind="turn", **keys, node_id=turn_id, widths=POPOVER)
            count("NodeNumbers.turn")
        calls = rows_of(
            store, f"SELECT session_id, source, id AS api_call_id FROM live_api_calls {sample}", {}
        )
        for keys in calls:
            tools = store.nodes.children(ToolRow, keys, skipped=0, size=50, widths=LOG)
            assert all(isinstance(row, ToolRow) for row in tools.rows)
            count("ToolRow", len(tools.rows))
            api_call_id = keys.pop("api_call_id")
            store.nodes.numbers(kind="call", **keys, node_id=api_call_id, widths=POPOVER)
            count("NodeNumbers.call")
        # The bucket arm: a thread with api calls answering no turn pages them at `turn_id`
        # NULL, so every such thread is read once and its page must hold every one of them.
        buckets = rows_of(
            store,
            f"SELECT * FROM (SELECT DISTINCT session_id, source FROM live_api_calls"
            f" WHERE turn_id IS NULL) {sample}",
            {},
        )
        assert buckets, "the archive holds no unattributed api call, so the bucket arm ran dry"
        for thread in buckets:
            unattributed = store.nodes.children(
                CallRow, {**thread, "turn_id": None}, skipped=0, size=50, widths=LOG
            )
            assert all(isinstance(row, CallRow) for row in unattributed.rows)
            assert unattributed.rows, f"a thread with unattributed calls paged none: {thread}"
            count("CallRow.bucket", len(unattributed.rows))
        runs = rows_of(store, f"SELECT session_id, id AS run_id FROM live_agent_runs {sample}", {})
        for keys in runs:
            store.nodes.numbers(
                kind="run",
                session_id=keys["session_id"],
                source=keys["run_id"],
                node_id=keys["run_id"],
                widths=POPOVER,
            )
            count("NodeNumbers.run")
        for keys in rows_of(store, f"SELECT session_id FROM session_rollups {sample}", {}):
            store.nodes.numbers(
                kind="session",
                session_id=keys["session_id"],
                source=MAIN,
                node_id=keys["session_id"],
                widths=POPOVER,
            )
            count("NodeNumbers.session")
        tools = rows_of(
            store,
            f"SELECT session_id, source, id AS tool_call_id FROM live_tool_calls {sample}",
            {},
        )
        for keys in tools:
            assert store.nodes.tool_numbers(**keys, widths=POPOVER) is not None
            count("ToolNumbers")
        marks = rows_of(
            store,
            f"SELECT session_id, source, id AS compaction_id FROM live_compactions {sample}",
            {},
        )
        for keys in marks:
            assert store.nodes.compaction_numbers(**keys, widths=POPOVER) is not None
            count("CompactionNumbers")
        lines = rows_of(store, f"SELECT session_id, source, line_no FROM raw_records {sample}", {})
        for keys in lines:
            assert store.nodes.record(**keys) is not None
            count("WholeRecord")
    print(f"\n{LIVE_STORE}: {counts}")  # noqa: T201 — the counts a person runs this for
