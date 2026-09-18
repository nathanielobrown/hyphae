"""`AnalysisRepository`: the `hp query` read — a corpus scoped once, then a statement by name.

Driven against the corpus store, over the seam the runner reads through: `scope` builds the
two relations every corpus statement reads, in the order the second needs the first, and
counts what the predicate could not place; `run` answers a statement whole — the header in
statement order, the rows as tuples — with a citation that names what scoped the corpus ahead
of what the statement bound. The literals are what `hp query` printed for the same calls
before the read moved into the store, so a swapped header or a re-keyed citation is a red here
before it is a changed byte on stdout.

The `HYPHAE_LIVE_STORE` leaf at the end is the backstop over the real archive, as in
`tests/store/test_sessions.py`: off by default, run by hand before the PR opens.
"""

import datetime as dt
import os
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest

from hyphae.models.analysis import Answered
from hyphae.models.citation import Citation
from hyphae.store import analysis, library
from hyphae.store.analysis import AnalysisRepository
from hyphae.store.handle import Store, open_store
from tests.analyze.conftest import MYCELIA_SESSIONS
from tests.conftest import MYCELIA, NO_WAIT, SPINE
from tests.store.test_handle import reached
from tests.store.test_sessions import AS_OF, LIVE_STORE, rows_of

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")

# The corpus statement and the keyed statement the leaves below run, with what each binds:
# the counts every report opens with, and one session's outline at the library's own width.
COUNTS = "session_counts"
TIMELINE = "session_timeline"
TIMELINE_BINDINGS: dict[str, Any] = {"session_id": SPINE, "log_chars": library.LOG_CHARS}
# What `scope` cites for the mycelia corpus at the fixture's date, in the order it binds them.
CORPUS: dict[str, Any] = {
    "project": MYCELIA,
    "since": None,
    "as_of": AS_OF,
    "window_days": library.WINDOW_DAYS,
}
# The one fixture session recorded with no `project_dir`, which no predicate can place.
UNPLACEABLE = 1


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    # A fresh handle per leaf, not a shared one: `scope` leaves temp tables on the connection,
    # and a leaf that reads before any scope has to see a connection none has touched.
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> AnalysisRepository:
    return store.analysis


def test_the_handle_hands_out_one_repository(store: Store) -> None:
    """`store.analysis` is the repository over that store, built once, scoped to nothing yet."""
    assert store.analysis is store.analysis
    assert isinstance(store.analysis, AnalysisRepository)
    assert store.analysis.store is store
    assert store.analysis.corpus == {}


# --- the corpus -------------------------------------------------------------------------------


def test_scope_builds_both_relations_and_counts_what_it_could_not_place(
    store: Store, repository: AnalysisRepository
) -> None:
    """After `scope`, `project_sessions` holds the project's sessions, `session_period` puts
    each in both windows, the bindings that defined them are remembered for the citation, and
    the count that comes back is the sessions no predicate can judge."""
    unplaceable = repository.scope(project=Path(MYCELIA), since=None, as_of=AS_OF)
    assert unplaceable == UNPLACEABLE
    assert repository.corpus == CORPUS
    # Every mycelia session is in the corpus, and each falls in the trailing window at the
    # fixture's date, so both periods count the same rows.
    assert rows_of(store, "SELECT count(*) AS n FROM project_sessions", {}) == [
        {"n": MYCELIA_SESSIONS}
    ]
    assert rows_of(
        store, "SELECT period, count(*) AS n FROM session_period GROUP BY ALL ORDER BY ALL", {}
    ) == [
        {"period": "corpus", "n": MYCELIA_SESSIONS},
        {"period": "trailing_window", "n": MYCELIA_SESSIONS},
    ]


def test_since_narrows_the_corpus_and_the_citation_says_so(
    store: Store, repository: AnalysisRepository
) -> None:
    """`since` cuts the corpus at a date, and is cited at that date rather than NULL."""
    since = dt.date(2026, 7, 15)
    repository.scope(project=Path(MYCELIA), since=since, as_of=AS_OF)
    assert rows_of(store, "SELECT count(*) AS n FROM project_sessions", {}) == [{"n": 7}]
    assert repository.corpus["since"] == since


def test_a_typed_path_is_resolved_before_it_scopes(
    store: Store, repository: AnalysisRepository
) -> None:
    """A project spelled with a trailing slash or a `..` names the corpus its resolved path
    does, and the citation quotes the resolved spelling."""
    repository.scope(project=Path(f"{MYCELIA}/../mycelia/"), since=None, as_of=AS_OF)
    assert repository.corpus["project"] == MYCELIA
    assert rows_of(store, "SELECT count(*) AS n FROM project_sessions", {}) == [
        {"n": MYCELIA_SESSIONS}
    ]


def test_the_period_view_is_built_after_the_table_it_reads(enriched_db: Path) -> None:
    """On a connection nothing scoped yet, the view over `project_sessions` can only be built
    once the table is: the order the two statements run in is the contract, and DuckDB refuses
    the other one."""
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as store:
        with pytest.raises(duckdb.CatalogException, match="project_sessions"):
            store.rows(analysis.SESSION_PERIODS, {})
        # The repository runs them in the order that works.
        store.analysis.scope(project=Path(MYCELIA), since=None, as_of=AS_OF)
        assert rows_of(store, "SELECT count(*) AS n FROM session_period", {}) == [
            {"n": 2 * MYCELIA_SESSIONS}
        ]


def test_a_corpus_statement_before_scope_is_refused_by_the_database(
    repository: AnalysisRepository,
) -> None:
    """`scope` is state a corpus statement reads: run one on a handle nothing scoped and DuckDB
    refuses it at the relation `scope` would have built, rather than answering over nothing."""
    with pytest.raises(duckdb.CatalogException, match="session_period"):
        repository.run(COUNTS, {})


# --- the answer ------------------------------------------------------------------------------


def test_a_corpus_statement_answers_what_hp_query_printed(
    repository: AnalysisRepository,
) -> None:
    """The counts over the mycelia corpus, whole: the header as the statement spells it, the
    rows as tuples, and the citation naming the corpus bindings ahead of the statement's."""
    repository.scope(project=Path(MYCELIA), since=None, as_of=AS_OF)
    answer = repository.run(COUNTS, {})
    assert answer == Answered(
        columns=(
            "period",
            "sessions",
            "turns",
            "api_calls",
            "tool_calls",
            "agent_runs",
            "compactions",
            "cost_usd",
            "unpriced_api_calls",
        ),
        rows=[
            ("corpus", 16, 25, 41, 42, 10, 7, 17.0153, 0),
            ("trailing_window", 16, 25, 41, 42, 10, 7, 17.0153, 0),
        ],
        citation=Citation(COUNTS, CORPUS),
    )
    assert list(answer.citation.bindings) == ["project", "since", "as_of", "window_days"]


def test_a_keyed_statement_answers_its_rows_and_cites_only_what_it_bound(
    store: Store, repository: AnalysisRepository
) -> None:
    """With no corpus scoped, a keyed statement's citation is its own bindings alone, in the
    order they were passed, and its rows are the statement's."""
    answer = repository.run(TIMELINE, TIMELINE_BINDINGS)
    columns, rows = store.rows(library.load(TIMELINE), TIMELINE_BINDINGS)
    assert rows, "the spine session lost its turns: re-pick the session"
    assert answer == Answered(columns, rows, Citation(TIMELINE, TIMELINE_BINDINGS))
    assert answer.columns[:2] == ("turn_index", "turn_id")
    assert list(answer.citation.bindings) == ["session_id", "log_chars"]


def test_a_corpus_statement_with_bindings_of_its_own_cites_them_after_the_corpus(
    repository: AnalysisRepository,
) -> None:
    """What scoped the corpus comes first, then what the statement bound: the order the line
    a report copies has always read in, and the one a reader pastes back."""
    repository.scope(project=Path(MYCELIA), since=None, as_of=AS_OF)
    answer = repository.run("co_occurrence", {"min_sessions": 3})
    assert answer.citation == Citation("co_occurrence", {**CORPUS, "min_sessions": 3})
    assert list(answer.citation.bindings) == [*CORPUS, "min_sessions"]
    assert library.citation(*answer.citation) == (
        f"-- queries/co_occurrence.sql project={MYCELIA} since=NULL as_of={AS_OF}"
        f" window_days={library.WINDOW_DAYS} min_sessions=3"
    )


def test_a_binding_the_statement_names_and_the_caller_left_out_is_refused(
    repository: AnalysisRepository,
) -> None:
    """The driver's own refusal, not a NULL bound in its place: the manifest resolves every
    parameter before the store sees a statement, and this is what stands behind it."""
    with pytest.raises(duckdb.Error, match="session_id"):
        repository.run(TIMELINE, {})


# --- refusals --------------------------------------------------------------------------------


def test_a_keyword_left_off_or_added_is_refused(repository: AnalysisRepository) -> None:
    """Both methods take exactly their arguments: a drifted call fails here, not in the runner."""
    scope: Callable[..., Any] = repository.scope
    run: Callable[..., Any] = repository.run
    whole: dict[str, Any] = {"project": Path(MYCELIA), "since": None, "as_of": AS_OF}
    scope(**whole)
    with pytest.raises(TypeError, match="missing"):
        scope(**{key: value for key, value in whole.items() if key != "since"})
    with pytest.raises(TypeError, match="unexpected keyword"):
        scope(**whole, window_days=7)
    # The corpus is keyword-only: three values of two types, so a positional call is a slip.
    with pytest.raises(TypeError, match="positional"):
        scope(*whole.values())
    with pytest.raises(TypeError, match="missing"):
        run(COUNTS)
    with pytest.raises(TypeError, match="unexpected keyword"):
        run(COUNTS, {}, project=MYCELIA)


# --- the boundary ----------------------------------------------------------------------------


@pytest.mark.reads_the_repo  # reads every module outside the store package
def test_the_runner_no_longer_reaches_the_handle() -> None:
    """`analyze/runner.py` reads through this repository now: the ratchet in
    `tests/store/test_handle.py` states the set, and this is the PR's own proof of its half."""
    assert "analyze/runner.py" not in reached()


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_one_corpus_and_one_keyed_statement_answer_over_the_real_archive(tmp_path: Path) -> None:
    """A corpus statement over the archive's own mycelia sessions and a keyed one over its
    busiest, both non-empty, with the citation shape the fixture leaves pin.

    Counts only: a timeline row is session content, and a failing assertion prints its
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
        (busiest,) = rows_of(
            store,
            "SELECT session_id FROM live_turns GROUP BY ALL ORDER BY count(*) DESC, session_id"
            " LIMIT 1",
            {},
        )
        keyed = store.analysis.run(
            TIMELINE, {"session_id": busiest["session_id"], "log_chars": library.LOG_CHARS}
        )
        assert keyed.rows, "the busiest session has no timeline row, so this proved nothing"
        assert list(keyed.citation.bindings) == ["session_id", "log_chars"]
        unplaceable = store.analysis.scope(
            project=Path(MYCELIA), since=None, as_of=dt.datetime.now(tz=dt.UTC).date()
        )
        counts = store.analysis.run(COUNTS, {})
        assert counts.columns[:2] == ("period", "sessions")
        assert [row[0] for row in counts.rows] == ["corpus", "trailing_window"]
        assert counts.rows[0][1] > 0, "the archive holds no mycelia session, so this proved nothing"
        assert list(counts.citation.bindings) == list(CORPUS)
    print(  # noqa: T201 — the counts a person runs this for
        f"\n{LIVE_STORE}: timeline rows={len(keyed.rows)} corpus={counts.rows[0][1]}"
        f" unplaceable={unplaceable}"
    )
