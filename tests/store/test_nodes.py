"""`NodeRepository`: one node's header as a strict model, and one of its fat values whole.

Driven against the corpus store, over the seam the node page reads through: a header row
of each kind reaches its model unchanged, at the widths the page and the expansion each
read at; a value comes back whole with the citation the fragment's footer quotes; a row the
store holds with nothing under it and a node the store never held are told apart; the
methods bind exactly what their statements declare; and the two tables that key them name
nothing a model lacks.

The `HYPHAE_LIVE_STORE` leaf at the end is the backstop over real shapes, as in
`tests/store/test_sessions.py`: off by default, run by hand before a PR touching a model opens.
"""

import dataclasses
import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation
from hyphae.models.node import CallHeader, NodeHeader, RunHeader, ToolHeader, TurnHeader
from hyphae.store import library, nodes
from hyphae.store.handle import Store, open_store
from hyphae.store.nodes import NodeRepository
from hyphae.store.trace_store import DuckDbExporter
from hyphae.view import bounds
from tests.conftest import (
    ANCESTOR,
    BASH_TOOL,
    DENSE_CALL,
    DENSE_TOOL,
    DENSE_TURN,
    FORK_ORIGIN,
    FORK_ORIGIN_RUN,
    MAIN,
    MARKDOWN_TOOL,
    NO_WAIT,
    SLASH_TURN,
    SPINE,
    SPINE_RUN,
    THREE_BAND_TURN,
)
from tests.store.test_sessions import LIVE_STORE, rows_of
from tests.view.conftest import MISSING

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")

# The two surfaces a header is read at, as the mappings a page passes: the pane, whose
# detail width is the URL's; and the expansion, whose widths carry the detail width too.
HEADER = bounds.HEADER_WIDTHS._asdict()
PAGE = {"detail_chars": bounds.DETAIL.default}
EXPANSION = bounds.EXPANSION_WIDTHS._asdict()
NO_SIZES: dict[str, int] = {}

# One node of each kind, by the keys its header statement binds: the spine's slash turn, the
# fork origin's own run, and the dense call and the `Read` it made.
TURN_KEYS = {"session_id": SPINE, "source": MAIN, "turn_id": SLASH_TURN}
RUN_KEYS = {"session_id": FORK_ORIGIN, "run_id": FORK_ORIGIN_RUN}
CALL_KEYS = {"session_id": FORK_ORIGIN, "source": FORK_ORIGIN_RUN, "api_call_id": DENSE_CALL}
TOOL_KEYS = {"session_id": FORK_ORIGIN, "source": FORK_ORIGIN_RUN, "tool_call_id": DENSE_TOOL}
SPINE_MAIN = {"session_id": SPINE, "source": MAIN}
KEYED: list[tuple[type[NodeHeader], dict[str, str]]] = [
    (TurnHeader, TURN_KEYS),
    (RunHeader, RUN_KEYS),
    (CallHeader, CALL_KEYS),
    (ToolHeader, TOOL_KEYS),
]
KINDS = ["turn", "run", "call", "tool"]

# Every value, the statement that reads it, and a node that holds it: the spine's three-band
# turn was typed, its slash turn followed a command, its run was spawned by a call with a
# prompt and a result, the fork's dense call spoke and thought, its `Read` was asked, the
# spine's `Read` of a Markdown file answered with a typed result, and the spine's `Bash` ran.
# The statement is spelled here rather than read off `nodes.VALUES`, so two entries of that
# table swapped are two reds here and not a table checked against itself.
HELD: list[tuple[type[NodeHeader], str, str, dict[str, str]]] = [
    (TurnHeader, "prompt", "view_turn_prompt", {**TURN_KEYS, "turn_id": THREE_BAND_TURN}),
    (TurnHeader, "command_args", "view_turn_command_args", TURN_KEYS),
    (RunHeader, "brief", "view_run_brief", RUN_KEYS),
    (RunHeader, "prompt", "view_run_prompt", {"session_id": SPINE, "run_id": SPINE_RUN}),
    (RunHeader, "result", "view_run_result", {"session_id": SPINE, "run_id": SPINE_RUN}),
    (CallHeader, "text", "view_call_text", CALL_KEYS),
    (CallHeader, "thinking", "view_call_thinking", CALL_KEYS),
    (ToolHeader, "input", "view_tool_input", TOOL_KEYS),
    (ToolHeader, "result", "view_tool_result", {**SPINE_MAIN, "tool_call_id": MARKDOWN_TOOL}),
    (ToolHeader, "command", "view_tool_command", {**SPINE_MAIN, "tool_call_id": BASH_TOOL}),
]


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> NodeRepository:
    return store.nodes


def test_the_handle_hands_out_one_repository(store: Store) -> None:
    """`store.nodes` is the repository over that store, built once."""
    assert store.nodes is store.nodes
    assert isinstance(store.nodes, NodeRepository)
    assert store.nodes.store is store


# --- row to model ---------------------------------------------------------------------------


@pytest.mark.parametrize(("model", "keys"), KEYED, ids=KINDS)
def test_a_header_row_reaches_its_model_unchanged(
    store: Store, repository: NodeRepository, model: type[NodeHeader], keys: dict[str, str]
) -> None:
    """A node's header is the statement's one row as a strict model, with its citation —
    bound keys first, then the width, then the size the URL asked, which is the order the
    footer quotes."""
    head = repository.header(model, keys, widths=HEADER, sizes=PAGE)
    assert head is not None
    statement = nodes.HEADERS[model]
    bindings = library.bind(statement, HEADER, PAGE, **keys)
    (raw,) = rows_of(store, library.load(statement), bindings)
    row = asdict(head)
    assert row.pop("citation") == Citation(statement, bindings)
    assert row == raw
    assert list(bindings) == [*keys, "head_chars", "detail_chars"]


@pytest.mark.parametrize(("model", "keys"), KEYED, ids=KINDS)
def test_an_expansion_reads_the_same_header_at_widths_of_its_own(
    repository: NodeRepository, model: type[NodeHeader], keys: dict[str, str]
) -> None:
    """The expansion's profile carries the detail width itself and asks no size, so the same
    node reads under it with no size at all — and the model is the same, at its widths."""
    expanded = repository.header(model, keys, widths=EXPANSION, sizes=NO_SIZES)
    assert expanded is not None
    assert expanded.citation == Citation(
        nodes.HEADERS[model], library.bind(nodes.HEADERS[model], EXPANSION, NO_SIZES, **keys)
    )


@pytest.mark.parametrize(("model", "keys"), KEYED, ids=KINDS)
def test_a_node_the_store_never_held_has_no_header(
    repository: NodeRepository, model: type[NodeHeader], keys: dict[str, str]
) -> None:
    """An unknown id is None outright, which the page turns into its 404."""
    unknown = {**keys, next(reversed(keys)): MISSING}
    assert repository.header(model, unknown, widths=HEADER, sizes=PAGE) is None


# --- the values ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "field", "statement", "keys"),
    HELD,
    ids=[f"{model.__name__}.{field}" for model, field, _, _ in HELD],
)
def test_a_value_is_read_whole_and_cites_the_statement_that_read_it(
    store: Store,
    repository: NodeRepository,
    model: type[NodeHeader],
    field: str,
    statement: str,
    keys: dict[str, str],
) -> None:
    """Each of the ten values comes back whole — the statement's one row under the strict
    build — with the statement and the keys it ran at, so the fragment prints the footer's
    line without naming a query. Only the named-file read binds a width beside its keys, and
    it is the only one that answers `result_type`, because it is the only statement that
    selects it (`tests/analyze/test_queries.py` holds that from the SQL side)."""
    assert nodes.VALUES[model, field] == statement
    whole = repository.value(model, field, keys, widths=HEADER)
    assert whole is not None
    assert whole.value
    bindings = library.bind(statement, HEADER, NO_SIZES, **keys)
    (raw,) = rows_of(store, library.load(statement), bindings)
    assert whole.value == raw["value"]
    assert whole.citation == Citation(statement, bindings)
    if (model, field) == (ToolHeader, "result"):
        assert whole.result_type == raw["result_type"] == ".md"
        assert list(bindings) == [*keys, "head_chars"]
    else:
        assert "result_type" not in raw
        assert whole.result_type is None
        assert list(bindings) == list(keys)


def test_a_row_with_nothing_under_it_and_a_missing_row_are_told_apart(
    repository: NodeRepository,
) -> None:
    """A turn nobody typed a slash at has the row and not the value, which the route turns
    into its 404; an id the store never held has no row at all."""
    blank = repository.value(
        TurnHeader,
        "command_args",
        {"session_id": ANCESTOR, "source": MAIN, "turn_id": DENSE_TURN},
        widths=HEADER,
    )
    assert blank is not None
    assert blank.value is None
    missing = {**TURN_KEYS, "turn_id": MISSING}
    assert repository.value(TurnHeader, "command_args", missing, widths=HEADER) is None


def test_a_store_nothing_was_extracted_into_answers_none(tmp_path: Path) -> None:
    """A store with the schema and no sessions has no header and no value, and refuses
    nothing."""
    db = tmp_path / "traces.duckdb"
    DuckDbExporter(db, wait=NO_WAIT)
    with open_store(db, read_only=True, wait=NO_WAIT) as store:
        assert store.nodes.header(TurnHeader, TURN_KEYS, widths=HEADER, sizes=PAGE) is None
        assert store.nodes.value(TurnHeader, "prompt", TURN_KEYS, widths=HEADER) is None


# --- the two tables ---------------------------------------------------------------------------


def test_every_header_model_is_keyed_and_every_value_is_a_field_its_header_cut() -> None:
    """`HEADERS` names a statement per header model, and `VALUES` a statement per value a
    header previews: the field it names is one the model carries, beside the count the
    header cut it to — so a value nobody's pane previews cannot be declared here."""
    assert set(nodes.HEADERS) == {TurnHeader, RunHeader, CallHeader, ToolHeader}
    assert len(nodes.VALUES) == 10
    for (model, field), statement in nodes.VALUES.items():
        fields = {one.name for one in dataclasses.fields(model)}
        assert {field, f"{field}_chars"} <= fields, (model, field)
        assert model in nodes.HEADERS
        assert statement.startswith("view_")
    assert len(set(nodes.VALUES.values())) == len(nodes.VALUES)


# --- refusals --------------------------------------------------------------------------------

# The two methods, each with one whole call, so a keyword can be dropped from or added to it.
HEADER_CALL: dict[str, Any] = {"widths": HEADER, "sizes": PAGE}
VALUE_CALL: dict[str, Any] = {"widths": HEADER}


def test_a_keyword_left_off_or_added_is_refused(repository: NodeRepository) -> None:
    """Each method binds exactly what its statements declare: the widths and the sizes are
    keyword-only, and the keys ride as one mapping rather than as keywords of their own."""
    header: Callable[..., Any] = repository.header
    header(TurnHeader, TURN_KEYS, **HEADER_CALL)
    with pytest.raises(TypeError, match="missing"):
        header(TurnHeader, TURN_KEYS, widths=HEADER)
    with pytest.raises(TypeError, match="unexpected keyword"):
        header(TurnHeader, TURN_KEYS, **HEADER_CALL, source=MAIN)
    with pytest.raises(TypeError, match="positional"):
        header(TurnHeader, TURN_KEYS, *HEADER_CALL.values())
    value: Callable[..., Any] = repository.value
    value(TurnHeader, "prompt", TURN_KEYS, **VALUE_CALL)
    with pytest.raises(TypeError, match="missing"):
        value(TurnHeader, "prompt", TURN_KEYS)
    with pytest.raises(TypeError, match="unexpected keyword"):
        value(TurnHeader, "prompt", TURN_KEYS, **VALUE_CALL, sizes=PAGE)
    with pytest.raises(TypeError, match="positional"):
        value(TurnHeader, "prompt", TURN_KEYS, *VALUE_CALL.values())


def test_a_key_or_a_width_the_statement_lacks_is_refused_by_the_binder(
    repository: NodeRepository,
) -> None:
    """The keys and the widths are held to the statement, in the binder's own words: a key
    the statement never named, a width short of what it binds, and a value the model never
    cut."""
    with pytest.raises(ValueError, match="binds no run_id"):
        repository.header(TurnHeader, RUN_KEYS, widths=HEADER, sizes=PAGE)
    with pytest.raises(ValueError, match="binds head_chars"):
        repository.header(TurnHeader, TURN_KEYS, widths={}, sizes=PAGE)
    with pytest.raises(ValueError, match="binds head_chars"):
        repository.value(ToolHeader, "result", TOOL_KEYS, widths=bounds.LOG_WIDTHS._asdict())
    with pytest.raises(KeyError):
        repository.value(TurnHeader, "started_at", TURN_KEYS, widths=HEADER)


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_every_header_and_value_of_the_real_archive_builds_its_model(tmp_path: Path) -> None:
    """Every turn and run of the archive on this machine, and a fixed sample of its api calls
    and tool calls, read as headers under the strict build at the page's widths; and every
    value of each of those nodes read whole.

    Counts only: a value is session content, and a failing assertion prints its operands. The
    archive is copied first, with its write-ahead log: a reader holding the archive open
    blocks the extract that writes it.
    """
    archive = Path(os.environ[LIVE_STORE])
    copy = tmp_path / archive.name
    shutil.copy(archive, copy)
    wal = archive.with_name(f"{archive.name}.wal")
    if wal.exists():
        shutil.copy(wal, copy.with_name(f"{copy.name}.wal"))
    # Which live rows key each kind: the whole of the two small tables, and a repeatable
    # reservoir of the two large ones, which run to hundreds of thousands.
    sample = "USING SAMPLE reservoir(1000 ROWS) REPEATABLE (46)"
    listed: dict[type[NodeHeader], str] = {
        TurnHeader: "SELECT session_id, source, id AS turn_id FROM live_turns",
        RunHeader: "SELECT session_id, id AS run_id FROM live_agent_runs",
        CallHeader: f"SELECT session_id, source, id AS api_call_id FROM live_api_calls {sample}",
        ToolHeader: f"SELECT session_id, source, id AS tool_call_id FROM live_tool_calls {sample}",
    }
    counts: dict[str, int] = {}
    spawned = {(RunHeader, "prompt"), (RunHeader, "result")}
    with open_store(copy, read_only=True, wait=NO_WAIT) as store:
        for model, sql in listed.items():
            keys = rows_of(store, sql, {})
            assert keys, f"the archive holds no {model.__name__}, so this leaf proved nothing"
            fields = [field for held, field in nodes.VALUES if held is model]
            for one in keys:
                head = store.nodes.header(model, one, widths=HEADER, sizes=PAGE)
                assert isinstance(head, model)
                for field in fields:
                    whole = store.nodes.value(model, field, one, widths=HEADER)
                    # A run no tool call spawned has no prompt and no result: the two JOIN.
                    assert whole is not None or (model, field) in spawned, (model, field)
                    counts[f"{model.__name__}.{field}"] = counts.get(
                        f"{model.__name__}.{field}", 0
                    ) + (whole is not None)
            counts[model.__name__] = len(keys)
    print(f"\n{LIVE_STORE}: {counts}")  # noqa: T201 — the counts a person runs this for
