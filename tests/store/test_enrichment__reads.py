"""What a page reads off the enrichment repository: whether the tables are there, one session's
rows cut for the pane, and one line whole — and the strict models every read builds.

The rows under test are the ones `enriched_db` planted over the fixture corpus, so the
statements answer over keys the pipeline really writes.
"""

import os
import shutil
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation
from hyphae.models.enrichment import ROWS, Described, Level
from hyphae.models.items import Item
from hyphae.models.node import WholeValue
from hyphae.models.row import ROW
from hyphae.models.trace import MAIN_SOURCE
from hyphae.store import library
from hyphae.store.enrichment import ENRICHMENT, LINE_STATEMENTS, EnrichmentRepository
from hyphae.store.handle import open_store
from hyphae.view import bounds
from tests.conftest import NO_WAIT, enriching
from tests.enrich.conftest import SPINE, SPINE_RUN
from tests.store.test_handle import reached
from tests.store.test_sessions import LIVE_STORE, rows_of

# The widths the one enrichment surface prints at, as a page passes them.
ENRICHMENT_WIDTHS = bounds.ENRICHMENT_WIDTHS._asdict()


def test_the_handle_hands_out_one_repository(corpus_db: Path) -> None:
    """`store.enrichment` is the repository over that store, built once, for a page and a pass
    alike."""
    with open_store(corpus_db, read_only=True, wait=NO_WAIT) as store:
        assert store.enrichment is store.enrichment
        assert isinstance(store.enrichment, EnrichmentRepository)
        assert store.enrichment.store is store


def test_held_asks_the_catalog_for_the_tables(corpus_db: Path, enriched_db: Path) -> None:
    """A store no pass has prepared holds no enrichment table; a prepared one holds all three."""
    # If a page opens the store no pass has touched, the repository says so without a read...
    with open_store(corpus_db, read_only=True, wait=NO_WAIT) as store:
        assert store.enrichment.held() is False
    # ...and over the same corpus a pass prepared, the tables are there.
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as store:
        assert store.enrichment.held() is True


@pytest.mark.parametrize("level", sorted(ROWS), ids=str)
def test_a_store_missing_any_one_table_is_not_held(
    level: Level, enriched_db: Path, tmp_path: Path
) -> None:
    """Every enrichment table has to be there, whichever one is gone."""
    # If one level's table is dropped from a copy of the described store...
    partial = tmp_path / "partial.duckdb"
    shutil.copyfile(enriched_db, partial)
    with open_store(partial, read_only=False, wait=NO_WAIT) as store:
        store.rows(f"DROP TABLE {ROWS[level].table}", {})
    # ...then the repository holds nothing, since a page reads all three in one statement.
    with open_store(partial, read_only=True, wait=NO_WAIT) as store:
        assert store.enrichment.held() is False


@pytest.mark.parametrize(
    ("source", "levels"),
    [(MAIN_SOURCE, {"turn", "agent_run", "session"}), (SPINE_RUN, {"agent_run", "session"})],
    ids=["main", "run"],
)
def test_described_builds_every_row_by_column_name_and_cites_the_read(
    source: str, levels: set[str], enriched_db: Path
) -> None:
    """One session's rows at every level, exactly as the statement answers them for the thread
    asked, with the bindings the footer quotes."""
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as store:
        answer = store.enrichment.described(
            session_id=SPINE, source=source, widths=ENRICHMENT_WIDTHS
        )
        bindings = library.bind(ENRICHMENT, ENRICHMENT_WIDTHS, {}, session_id=SPINE, source=source)
        raw = rows_of(store, library.load(ENRICHMENT), bindings)
    # If the fixture corpus was enriched on all but the last item of each level...
    assert [asdict(row) for row in answer.rows] == raw
    # ...then `spine/` is described at all three levels under `main`, and a pass describes no
    # turn of the run's own thread, so under the run only the run and the session answer...
    assert {row.level for row in answer.rows} == levels
    # ...and the citation carries the widths beside the keys, as `library.bind` ordered them.
    assert answer == Described(answer.rows, Citation(ENRICHMENT, bindings))


def test_described_over_a_session_no_pass_reached_is_empty_and_still_cited(
    enriched_db: Path,
) -> None:
    """A session with no row is an empty answer, cited: the store held the tables to ask."""
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as store:
        answer = store.enrichment.described(
            session_id="no-such-session", source=MAIN_SOURCE, widths=ENRICHMENT_WIDTHS
        )
    assert answer.rows == []
    assert answer.citation.name == ENRICHMENT


# What a line's fetch route carries, by level: the item's primary key under the names the
# route spells, which is where a run's `agent_run_id` column is `run_id`.
ROUTE_KEYS = {
    Level.turn: ("session_id", "source", "turn_id"),
    Level.agent_run: ("session_id", "run_id"),
    Level.session: ("session_id",),
}


def keys_of(item: Item) -> dict[str, str]:
    """An item's primary key as the line's route carries it."""
    return dict(zip(ROUTE_KEYS[item.level], item.key_values, strict=True))


@pytest.mark.parametrize(
    ("level", "field"),
    sorted(LINE_STATEMENTS),
    ids=lambda part: str(part) if isinstance(part, Level) else part,
)
def test_line_answers_the_planted_line_whole_and_none_where_no_pass_wrote_one(
    enriched_db: Path, level: Level, field: str
) -> None:
    """Each of the six lines comes back whole from its own level's table, cited by its keys."""
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as store:
        repository = store.enrichment
        # If the first item of a level was planted with the row `planted_enrichment(0)` writes
        # — a description, and friction on every fourth index, so on this one...
        items = repository.items(level)
        first, last = keys_of(items[0]), keys_of(items[-1])
        planted = {"description": "Planted description 0.", "friction": "Planted friction."}
        # ...then the line comes back whole, cited by the keys alone: the statement binds no
        # width...
        assert repository.line(level, field, first) == WholeValue(
            value=planted[field], citation=Citation(LINE_STATEMENTS[level, field], first)
        )
        # ...and the last item of every level, which the planting skipped, has no line.
        assert repository.line(level, field, last) is None


def test_a_line_binds_only_the_keys_its_level_declares(enriched_db: Path) -> None:
    """A turn's keys name a thread; a session's do not. Keys the statement lacks are refused
    where the line is read, not in DuckDB with the parameter unnamed."""
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as store:
        repository = store.enrichment
        turn = keys_of(repository.items(Level.turn)[0])
        with pytest.raises(ValueError, match="source"):
            repository.line(Level.session, "description", turn)
        with pytest.raises(ValueError, match="turn_id"):
            repository.line(Level.turn, "friction", {"session_id": turn["session_id"]})
        # A field no pass writes names no statement.
        with pytest.raises(KeyError):
            repository.line(Level.turn, "category", turn)


def test_a_described_keyword_left_off_or_added_is_refused(enriched_db: Path) -> None:
    """`described` takes exactly its three keywords: a width spelled as a key is two surfaces."""
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as store:
        described: Callable[..., Any] = store.enrichment.described
        whole: dict[str, Any] = {
            "session_id": SPINE,
            "source": MAIN_SOURCE,
            "widths": ENRICHMENT_WIDTHS,
        }
        described(**whole)
        with pytest.raises(TypeError, match="missing"):
            described(**{key: value for key, value in whole.items() if key != "source"})
        with pytest.raises(TypeError, match="unexpected keyword"):
            described(**whole, head_chars=10)
        with pytest.raises(TypeError, match="positional"):
            described(*whole.values())
        # ...and a key spelled among the widths is an override of the surface, refused by name.
        with pytest.raises(ValueError, match="source"):
            described(**{**whole, "widths": {**ENRICHMENT_WIDTHS, "source": MAIN_SOURCE}})


# --- the items, strictly ----------------------------------------------------------------------


@pytest.mark.parametrize("level", list(Level))
def test_every_item_of_a_level_is_built_under_the_strict_model(
    fixture_db: Path, level: Level
) -> None:
    """The store selects every item into its model strictly: a column whose type drifted from
    the field's raises at the read, over every item the fixtures hold."""
    with enriching(fixture_db) as store:
        items = store.items(level)
    # If the fixtures hold items at this level...
    assert items
    # ...then each is its level's model, built with no coercion, and names its level.
    assert {item.level for item in items} == {level}
    assert all(getattr(type(item), "__pydantic_config__") == ROW for item in items)  # noqa: B009


# --- the boundary ----------------------------------------------------------------------------


@pytest.mark.reads_the_repo  # reads every module outside the store package
def test_the_viewer_no_longer_reaches_the_handle() -> None:
    """`view/enrichment.py` reads through this repository now: the ratchet in
    `tests/store/test_handle.py` states the set, and this is the PR's own proof of its half."""
    assert "view/enrichment.py" not in reached()


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_every_item_and_every_line_builds_over_the_real_archive(tmp_path: Path) -> None:
    """Every item of every level, and one described session with its lines, over the archive
    on this machine, under the strict build.

    The fixture corpus cannot split strict from lax on an item: no `Decimal`, no int for a
    float. Counts only — a description is a model's sentence about private work.
    """
    archive = Path(os.environ[LIVE_STORE])
    # A private copy with its write-ahead log, never the archive: a reader holding it open
    # blocks the extract that writes it, and `prepare` writes.
    copy = tmp_path / archive.name
    shutil.copy(archive, copy)
    if (wal := archive.with_suffix(archive.suffix + ".wal")).exists():
        shutil.copy(wal, copy.with_suffix(copy.suffix + ".wal"))
    with enriching(copy) as store:
        counts = {level: len(store.items(level)) for level in Level}
        sessions = store.items(Level.session)
        described = 0
        lines = 0
        for session in sessions:
            answer = store.described(
                session_id=keys_of(session)["session_id"],
                source=MAIN_SOURCE,
                widths=ENRICHMENT_WIDTHS,
            )
            described += len(answer.rows)
            for row in answer.rows:
                if row.level == Level.session:
                    lines += store.line(Level.session, "description", keys_of(session)) is not None
    print(f"\n{LIVE_STORE}: items={counts} described rows={described} session lines={lines}")  # noqa: T201 — the counts a person runs this for
    assert all(count > 0 for count in counts.values())
    assert lines <= described
