"""`SessionRepository`: the session list, the projects and one session's header, as models.

Every method is driven against the corpus store, and what is pinned is the seam a page reads
through: that a row reaches its model unchanged under a strict build (`dataclasses.asdict`
of the model is the row), that a column NULL for a session no pass reached is `None` on the
model rather than a refusal, that each method binds exactly what its statement declares — a
keyword left off or added raises before any page runs — and that each hands back the
citation a footer prints. The values are the fixture corpus's; `tests/fixtures/*/README.md`
names the session behind each.

The `HYPHAE_LIVE_STORE` leaf at the end is the only evidence over real shapes: the fixture
corpus holds no `Decimal`, no `date` for a `datetime` and no int for a float, so nothing
here can split strict from lax. Off by default — the store is private session data — and run
by hand against a copy of the archive before a PR that touches a model opens.
"""

import datetime as dt
import os
import shutil
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation
from hyphae.models.listing import (
    DescribedSessionRollup,
    Listing,
    Project,
    ProjectRollup,
    ProjectRollups,
    SessionHeader,
    SessionRollup,
)
from hyphae.store import library, sessions
from hyphae.store.handle import Store, open_store
from hyphae.store.sessions import PAGER_PROBE, SORTS, SessionRepository
from hyphae.store.trace_store import StoreExporter
from hyphae.view import bounds
from hyphae.view.enrichment import enriched
from tests.conftest import INVENTED_PROJECT_SESSION, MYCELIA, NO_WAIT, SPINE

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")

# The surfaces a page reads each method at, as the mapping a page passes.
LIST = bounds.LIST_WIDTHS._asdict()
PROJECTS = bounds.PROJECTS_WIDTHS._asdict()
HEADER = bounds.HEADER_WIDTHS._asdict()
# A day inside the fixture corpus's span, so the rollups' trailing windows hold sessions: at
# `utcnow()` every window column of the July-2026 corpus is NULL.
AS_OF = dt.date(2026, 7, 28)
# Names a real trace store for the backstop below. Off by default: the store holds private
# session data (`docs/store.md`).
LIVE_STORE = "HYPHAE_LIVE_STORE"


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> SessionRepository:
    return store.sessions


def rows_of(store: Store, sql: str, bindings: dict[str, Any]) -> list[dict[str, Any]]:
    """What a statement answers, as the dicts a model is built from."""
    columns, rows = store._rows(sql, bindings)
    return [dict(zip(columns, row, strict=True)) for row in rows]


def total_sessions(store: Store) -> int:
    """How many sessions the store lists: the rollup table, which `view_sessions` reads whole."""
    return rows_of(store, "SELECT count(*) AS n FROM session_rollups", {})[0]["n"]


def test_the_handle_hands_out_one_repository(store: Store) -> None:
    """`store.sessions` is the repository over that store, built once."""
    assert store.sessions is store.sessions
    assert isinstance(store.sessions, SessionRepository)
    assert store.sessions.store is store


# --- row to model ---------------------------------------------------------------------------


def test_a_listing_row_reaches_its_model_unchanged(
    store: Store, repository: SessionRepository
) -> None:
    """A page of the list is the composed statement's rows, one strict model per row."""
    listed = repository.listing(
        sort="started_at",
        direction="desc",
        page=1,
        size=total_sessions(store),
        filters={},
        widths=LIST,
        described=True,
    )
    raw = rows_of(
        store,
        sessions.composed("started_at", "desc", {}, described=True),
        {
            "limit": total_sessions(store) + PAGER_PROBE,
            "offset": 0,
            "head_chars": LIST["head_chars"],
            "item_chars": LIST["item_chars"],
            "head_items": LIST["head_items"],
            **library.bind(sessions.DESCRIBED_SESSIONS, LIST, {}),
        },
    )
    assert [asdict(row) for row in listed.rows] == raw
    assert all(isinstance(row, DescribedSessionRollup) for row in listed.rows)
    # ...and over a store no pass touched, the same rows without the joined half.
    plain = repository.listing(
        sort="started_at",
        direction="desc",
        page=1,
        size=total_sessions(store),
        filters={},
        widths=LIST,
        described=False,
    )
    assert [type(row) for row in plain.rows] == [SessionRollup] * len(raw)
    assert [asdict(row) for row in plain.rows] == [
        {key: value for key, value in row.items() if key in asdict(plain.rows[0])} for row in raw
    ]


def test_a_project_row_reaches_its_model_unchanged(
    store: Store, repository: SessionRepository
) -> None:
    projects = repository.projects(widths=LIST)
    bindings = library.bind(sessions.PROJECTS, LIST, {})
    assert [asdict(row) for row in projects.rows] == rows_of(
        store, library.load(sessions.PROJECTS), bindings
    )
    assert projects.citation == Citation(sessions.PROJECTS, bindings)


def test_a_rollup_row_reaches_its_model_unchanged(
    store: Store, repository: SessionRepository
) -> None:
    rollups = repository.rollups(as_of=AS_OF, widths=PROJECTS)
    bindings = library.bind(sessions.PROJECT_ROLLUPS, PROJECTS, {}, as_of=AS_OF)
    assert [asdict(row) for row in rollups.rows] == rows_of(
        store, library.load(sessions.PROJECT_ROLLUPS), bindings
    )
    assert rollups.citation == Citation(sessions.PROJECT_ROLLUPS, bindings)


def test_a_header_row_reaches_its_model_unchanged(
    store: Store, repository: SessionRepository
) -> None:
    head = repository.header(session_id=SPINE, widths=HEADER)
    bindings = library.bind(sessions.SESSION_HEADER, HEADER, {}, session_id=SPINE)
    assert head is not None
    # The model carries its citation beside the row's columns, and nothing else.
    (raw,) = rows_of(store, library.load(sessions.SESSION_HEADER), bindings)
    assert asdict(head) == {**raw, "citation": Citation(sessions.SESSION_HEADER, bindings)}


# --- the values ------------------------------------------------------------------------------


def test_the_spine_sessions_header(repository: SessionRepository) -> None:
    """One session's header whole, as the fixture README records it."""
    assert repository.header(session_id=SPINE, widths=HEADER) == SessionHeader(
        session_id=SPINE,
        title="fixture-title-2",
        project_dir=MYCELIA,
        project_filter=MYCELIA,
        git_branch="fixture-branch-1",
        version="2.1.221",
        entrypoint="cli",
        started_at=dt.datetime(2026, 7, 6, 19, 10, 55, 881000, tzinfo=dt.UTC),
        ended_at=dt.datetime(2026, 8, 6, 18, 41, 14, 84000, tzinfo=dt.UTC),
        wall_ms=2676618203,
        active_ms=219585,
        turns=6,
        api_calls=10,
        tool_calls=12,
        agent_runs=2,
        compactions=0,
        tool_errors=0,
        cost_usd=3.1675,
        unpriced_api_calls=0,
        input_tokens=17,
        output_tokens=5846,
        cache_read_tokens=362120,
        cache_creation_tokens=145722,
        skills=["grill-me", "night-run"],
        skills_cut=0,
        pr_urls=["fixture-pr-url-1"],
        pr_urls_cut=0,
        # `added` is what a turn grew the window by, which a session has no one answer for.
        context={"fill": 96258, "added": None, "window": 200000},
        citation=Citation(
            sessions.SESSION_HEADER,
            {"session_id": SPINE, "head_chars": 100, "item_chars": 60, "head_items": 5},
        ),
    )


@pytest.mark.parametrize("session_id", ["not-a-session", ""], ids=["unknown", "empty"])
def test_a_session_the_store_lacks_has_no_header(
    repository: SessionRepository, session_id: str
) -> None:
    """None, which the page turns into its 404 — never a model over no row."""
    assert repository.header(session_id=session_id, widths=HEADER) is None


def test_the_mycelia_rollup_inside_the_corpus_window(repository: SessionRepository) -> None:
    """Bound to a day the corpus spans, the trailing windows hold sessions and cost."""
    rollups = repository.rollups(as_of=AS_OF, widths=PROJECTS)
    (mycelia,) = [row for row in rollups.rows if row.project_dir == MYCELIA]
    assert mycelia == ProjectRollup(
        project_dir=MYCELIA,
        project_filter=MYCELIA,
        recent_sessions=2,
        recent_cost=0.9603,
        recent_unpriced=0,
        window_sessions=16,
        window_cost=17.0153,
        window_unpriced=0,
        sessions=16,
        cost_usd=17.0153,
        unpriced_api_calls=0,
        last_active=dt.datetime(2026, 7, 27, 14, 59, 18, 487000, tzinfo=dt.UTC),
        matched_rows=4,
    )
    # The page is under its limit, so the landing page cut nothing.
    assert rollups == ProjectRollups(rows=rollups.rows, cut=0, citation=rollups.citation)
    assert len(rollups.rows) == 4


def test_the_landing_page_says_how_many_projects_its_limit_left_off(
    repository: SessionRepository,
) -> None:
    """Bound below the corpus's four projects, the rollups carry the rows the limit dropped
    as a count, and every row still says how many the statement matched."""
    rollups = repository.rollups(as_of=AS_OF, widths={**PROJECTS, "projects": 1})
    assert len(rollups.rows) == 1
    assert rollups.cut == 3
    assert rollups.rows[0].matched_rows == 4


def test_the_projects_the_filter_box_suggests(repository: SessionRepository) -> None:
    """Every project the corpus names, busiest first."""
    assert repository.projects(widths=LIST).rows == [
        Project(MYCELIA, 16),
        Project("/invented/project", 1),
        Project("/repo", 1),
    ]


def test_a_session_no_pass_reached_lists_with_nothing_said(
    store: Store, repository: SessionRepository
) -> None:
    """The joined half is NULL for a session outside every enrichment table, and the model
    holds `None` there rather than refusing the row."""
    listed = repository.listing(
        sort="started_at",
        direction="desc",
        page=1,
        size=total_sessions(store),
        filters={},
        widths=LIST,
        described=True,
    )
    (unreached,) = [row for row in listed.rows if row.session_id == INVENTED_PROJECT_SESSION]
    assert isinstance(unreached, DescribedSessionRollup)
    assert (
        unreached.description,
        unreached.category,
        unreached.outcome,
        unreached.work,
        unreached.work_cut,
    ) == (None, None, None, None, None)
    # ...while a session whose turns a pass reached but whose own row it did not has work to
    # show and nothing said about it: the join lists it with an empty description.
    partial = [
        row
        for row in listed.rows
        if isinstance(row, DescribedSessionRollup) and row.description is None and row.work
    ]
    assert partial and all(row.work_cut == 0 for row in partial)


def test_every_method_over_a_store_nothing_was_extracted_into(tmp_path: Path) -> None:
    """A store with the schema and no sessions answers every read empty, and refuses none."""
    db = tmp_path / "traces.duckdb"
    StoreExporter(db, wait=NO_WAIT)
    with open_store(db, read_only=True, wait=NO_WAIT) as store:
        repository = store.sessions
        listed = repository.listing(
            sort="title",
            direction="asc",
            page=1,
            size=1,
            filters={},
            widths=LIST,
            described=False,
        )
        assert listed == Listing(rows=[], more=False, ran=listed.ran)
        assert repository.projects(widths=LIST).rows == []
        # No rows means no `matched_rows` to read the cut off, and nothing was cut.
        rollups = repository.rollups(as_of=AS_OF, widths=PROJECTS)
        assert rollups == ProjectRollups(rows=[], cut=0, citation=rollups.citation)
        assert repository.header(session_id=SPINE, widths=HEADER) is None


# --- paging and sorting ----------------------------------------------------------------------


def test_the_list_says_whether_a_page_follows(store: Store, repository: SessionRepository) -> None:
    """One row past the page is read and dropped: `more` is whether it was there."""
    total = total_sessions(store)

    def page(size: int) -> Listing:
        return repository.listing(
            sort="started_at",
            direction="desc",
            page=1,
            size=size,
            filters={},
            widths=LIST,
            described=False,
        )

    # A page one short of the corpus has a row after it...
    short = page(total - 1)
    assert (len(short.rows), short.more) == (total - 1, True)
    # ...and a page the size of the corpus does not, and hands back no probe row.
    whole = page(total)
    assert (len(whole.rows), whole.more) == (total, False)
    assert PAGER_PROBE == 1


def test_the_sorts_the_list_offers() -> None:
    """The columns a URL may sort by, which the routes hold a `?sort=` to."""
    assert SORTS == (
        "started_at",
        "title",
        "project_dir",
        "turns",
        "api_calls",
        "tool_calls",
        "compactions",
        "tool_errors",
        "cost_usd",
        "wall_ms",
        "agent_runs",
    )


def test_a_sort_or_filter_the_list_does_not_offer_is_refused(repository: SessionRepository) -> None:
    """A word outside `SORTS` or `FILTERS` never reaches the statement, and the refusal names
    the sort it was asked for."""
    for sort, filters in [("banana", {}), ("title", {"banana": 1})]:
        with pytest.raises(KeyError, match=sort):
            repository.listing(
                sort=sort,
                direction="asc",
                page=1,
                size=1,
                filters=filters,
                widths=LIST,
                described=False,
            )


def test_a_listing_cites_what_it_ran(repository: SessionRepository) -> None:
    """The composed statement at its window and widths, then the joined one at its own."""
    listed = repository.listing(
        sort="cost_usd",
        direction="asc",
        page=2,
        size=5,
        filters={"project": MYCELIA},
        widths=LIST,
        described=True,
    )
    assert listed.ran == [
        Citation(
            sessions.SESSIONS,
            {
                "sort": "cost_usd",
                "direction": "asc",
                "limit": 5,
                "offset": 5,
                "head_chars": 100,
                "item_chars": 20,
                "head_items": 4,
                "project": MYCELIA,
            },
        ),
        Citation(
            sessions.DESCRIBED_SESSIONS,
            {"head_chars": 100, "tag_chars": 20, "kind_chars": 20, "head_kinds": 3},
        ),
    ]
    # ...and only the first over a store with nothing to join.
    plain = repository.listing(
        sort="cost_usd",
        direction="asc",
        page=2,
        size=5,
        filters={"project": MYCELIA},
        widths=LIST,
        described=False,
    )
    assert plain.ran == listed.ran[:1]


# --- refusals --------------------------------------------------------------------------------

# Every method with one whole call, so a keyword can be dropped from it or added to it.
CALLS: dict[str, dict[str, Any]] = {
    "listing": {
        "sort": "title",
        "direction": "asc",
        "page": 1,
        "size": 1,
        "filters": {},
        "widths": LIST,
        "described": False,
    },
    "projects": {"widths": LIST},
    "rollups": {"as_of": AS_OF, "widths": PROJECTS},
    "header": {"session_id": SPINE, "widths": HEADER},
}


@pytest.mark.parametrize("method", sorted(CALLS))
def test_a_keyword_left_off_or_added_is_refused(repository: SessionRepository, method: str) -> None:
    """A method binds exactly what its statement declares, keyword by keyword: a drifted
    signature fails here before any page runs."""
    call = CALLS[method]
    # The whole call runs...
    getattr(repository, method)(**call)
    # ...one keyword short, it does not...
    with pytest.raises(TypeError, match="missing"):
        getattr(repository, method)(
            **{key: value for key, value in call.items() if key != "widths"}
        )
    # ...nor with one it never named...
    with pytest.raises(TypeError, match="unexpected keyword"):
        getattr(repository, method)(**call, turn_id="t")
    # ...nor positionally: the keywords are the contract.
    with pytest.raises(TypeError, match="positional"):
        getattr(repository, method)(*call.values())


@pytest.mark.parametrize("method", sorted(set(CALLS) - {"listing"}))
def test_a_surface_short_of_a_width_is_refused_by_the_binder(
    repository: SessionRepository, method: str
) -> None:
    """The widths are held to the statement too, in the binder's own words."""
    call = CALLS[method]
    short = {key: value for key, value in call["widths"].items() if key != "head_chars"}
    with pytest.raises(ValueError, match="binds head_chars"):
        getattr(repository, method)(**{**call, "widths": short})


def test_the_list_binds_its_own_widths_by_name(repository: SessionRepository) -> None:
    """The composed statement has no file to bind from, so the three widths it prints at are
    read off the surface by name — and a surface short of one is a `KeyError` on that name."""
    with pytest.raises(KeyError, match="head_items"):
        repository.listing(
            sort="title",
            direction="asc",
            page=1,
            size=1,
            filters={},
            widths={key: value for key, value in LIST.items() if key != "head_items"},
            described=False,
        )


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_every_method_builds_every_row_of_the_real_archive(tmp_path: Path) -> None:
    """Every row of every method, over the archive on this machine, under the strict build.

    The fixture corpus cannot split strict from lax, so this is the one place a real shape —
    a `Decimal`, a `date` where a `datetime` is due, an int for a float — would refuse. Counts
    only: a title is session content, and a failing assertion prints its operands.
    """
    archive = Path(os.environ[LIVE_STORE])
    # A private copy with its write-ahead log, never the archive: a reader holding it open
    # blocks the extract that writes it.
    copy = tmp_path / archive.name
    shutil.copy(archive, copy)
    wal = archive.with_name(f"{archive.name}.wal")
    if wal.exists():
        shutil.copy(wal, copy.with_name(f"{copy.name}.wal"))
    with open_store(copy, read_only=True, wait=NO_WAIT) as store:
        repository = store.sessions
        total = total_sessions(store)
        listed = repository.listing(
            sort="started_at",
            direction="desc",
            page=1,
            size=total,
            filters={},
            widths=LIST,
            described=enriched(store),
        )
        projects = repository.projects(widths=LIST)
        rollups = repository.rollups(as_of=dt.datetime.now(dt.UTC).date(), widths=PROJECTS)
        heads = [repository.header(session_id=row.session_id, widths=HEADER) for row in listed.rows]
    counts = {
        "sessions": len(listed.rows),
        "described": sum(
            isinstance(row, DescribedSessionRollup) and row.description is not None
            for row in listed.rows
        ),
        "projects": len(projects.rows),
        "rollups": len(rollups.rows),
        "headers": sum(head is not None for head in heads),
    }
    print(f"\n{LIVE_STORE}: {counts}")  # noqa: T201 — the counts a person runs this for
    assert counts["sessions"] == total > 0
    assert counts["headers"] == total
