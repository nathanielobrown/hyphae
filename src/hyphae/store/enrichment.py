"""The enrichment tables, and everything that reads or writes them.

These tables live in the same DuckDB file as the trace store but outside the pipeline's
per-session replace, so a re-extraction never touches them. They attach to the pipeline's
natural keys, which come from the data and survive re-extraction with it.

`EnrichmentRepository` is the handle's `enrichment` property (`store/handle.py`), for both of
its readers. A pass opens the store writable, calls `prepare` once, then asks it for the items of
a level and hands back rows to render; a level's `Stamp`s are what each stored row was
written under, for `enrich/stamp.py` to judge. A page holds a read-only handle, never
prepares, and reads what the pass wrote: `held` says whether the tables are there at all,
`described` reads one session's rows at every level, and `line` reads one of them whole.
"""

import datetime as dt
from collections.abc import Mapping
from dataclasses import astuple, fields
from typing import TYPE_CHECKING

import duckdb

from hyphae.models.citation import Citation
from hyphae.models.enrichment import COLUMNS as STAMP_COLUMNS
from hyphae.models.enrichment import ROWS, Described, DescribedItem, Enrichment, Level, Stamp
from hyphae.models.items import (
    AgentRunItem,
    Item,
    SessionItem,
    TurnItem,
    item_key,
)
from hyphae.models.node import WholeValue
from hyphae.store import library
from hyphae.store.items import ItemReader
from hyphae.store.schema import check_shape

if TYPE_CHECKING:
    # The handle hands out this repository, and this repository holds the handle: the one cycle
    # the design has, so the name is the checker's only.
    from hyphae.store.handle import Store

# What one enrichment row is, past its primary key: the model's answer, the stamp it was
# written under, and when. In the order `upsert` binds them, and the one list the views
# project and the DDL below is held to (`tests/store/test_enrichment.py`).
PAYLOAD_COLUMNS: tuple[str, ...] = (
    *(field.name for field in fields(Enrichment)),
    *STAMP_COLUMNS,
    "enriched_at",
)

# Those columns as a view projects them off the enrichment table. The one rename is spelled
# here for all three views; `enriched_agent_runs` below says why `model` cannot keep its name.
_ENRICHMENT_PROJECTION = ", ".join(
    f"e.{column} AS enrichment_model" if column == "model" else f"e.{column}"
    for column in PAYLOAD_COLUMNS
)

# Every enrichment table holds the same columns; only the primary key differs.
_ENRICHMENT_COLUMNS = """
  description VARCHAR NOT NULL,
  category VARCHAR NOT NULL,
  outcome VARCHAR NOT NULL,
  -- One line of visible struggle, NULL when the records showed none.
  friction VARCHAR,
  -- The four fields that decide staleness: sha256 of the rendered prompt content, the
  -- level's prompt version, the taxonomy version, and the model that answered.
  input_hash VARCHAR NOT NULL,
  prompt_version INTEGER NOT NULL,
  taxonomy_version INTEGER NOT NULL,
  model VARCHAR NOT NULL,
  enriched_at TIMESTAMPTZ NOT NULL,
"""

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS turn_enrichments (
  session_id VARCHAR NOT NULL, source VARCHAR NOT NULL, turn_id VARCHAR NOT NULL,
  {_ENRICHMENT_COLUMNS}
  PRIMARY KEY (session_id, source, turn_id)
);
CREATE TABLE IF NOT EXISTS agent_run_enrichments (
  session_id VARCHAR NOT NULL, agent_run_id VARCHAR NOT NULL,
  {_ENRICHMENT_COLUMNS}
  PRIMARY KEY (session_id, agent_run_id)
);
CREATE TABLE IF NOT EXISTS session_enrichments (
  session_id VARCHAR NOT NULL,
  {_ENRICHMENT_COLUMNS}
  PRIMARY KEY (session_id)
);
-- The sessions enrichment describes, named once so the reader and the sweep cannot drift
-- apart: a session with no main turn and no agent run has nothing to describe, and one whose
-- turns drove no api call has no model response to describe. 45 recorded sessions are in the
-- second state — `/model` and `/effort` turns the CLI answered by itself — and the QC pass
-- found the model inventing work for them rather than reporting none.
CREATE OR REPLACE VIEW describable_sessions AS
SELECT * FROM session_rollups WHERE (turns > 0 OR agent_runs > 0) AND api_calls > 0;
-- LEFT join, so an un-enriched turn still appears and coverage reads honestly.
CREATE OR REPLACE VIEW enriched_turns AS
SELECT t.*, {_ENRICHMENT_PROJECTION}
FROM live_turns t
LEFT JOIN turn_enrichments e
  ON e.session_id = t.session_id AND e.source = t.source AND e.turn_id = t.id;
-- `agent_runs` carries a `model` of its own — the model that ran it — so it keeps its
-- meaning under a name that says whose it is, and `description` means the enrichment's in
-- all three views. The run's own brief needs no such rename: it is `brief`.
CREATE OR REPLACE VIEW enriched_agent_runs AS
SELECT r.* EXCLUDE (model), r.model AS agent_model, {_ENRICHMENT_PROJECTION}
FROM live_agent_runs r
LEFT JOIN agent_run_enrichments e
  ON e.session_id = r.session_id AND e.agent_run_id = r.id;
CREATE OR REPLACE VIEW enriched_sessions AS
SELECT r.*, {_ENRICHMENT_PROJECTION}
FROM session_rollups r
LEFT JOIN session_enrichments e ON e.session_id = r.session_id;
"""


# What a pass said about one session, its threads' turns and its runs: the rows a page shows
# beside each item. Absent from a store no pass has prepared, which is what `held` asks first.
ENRICHMENT = "view_enrichment"
# The two lines a pass wrote about an item, whole, at each of the three levels it writes at:
# one statement each, because a fetch serves one value and a reader opens whichever of the two
# ran past the width. Keyed by the level and the column, which is how a page's detail spec
# names the one it previews.
LINE_STATEMENTS: dict[tuple[Level, str], str] = {
    (Level.turn, "description"): "view_turn_description",
    (Level.turn, "friction"): "view_turn_friction",
    (Level.agent_run, "description"): "view_run_description",
    (Level.agent_run, "friction"): "view_run_friction",
    (Level.session, "description"): "view_session_description",
    (Level.session, "friction"): "view_session_friction",
}


class EnrichmentRepository:
    """Reads enrichable items out of a trace store and writes enrichments back to it.

    Over the handle the caller opened, on the caller's terms: a pass holds it writable and
    calls `prepare` before anything else; a page holds it read-only, so a write raises in
    DuckDB rather than landing. A plain class rather than a dataclass: mutmut skips every
    decorated class.
    """

    def __init__(self, store: "Store") -> None:
        self.store = store

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """The handle's own connection, for the SQL the readers and writers here run on it.

        The handle keeps its connection private; this is the planter's door to it — what a
        test that plants a row or reads a table back runs on — and no package outside the
        store reaches it (`tests/store/test_handle.py`).
        """
        return self.store._connection

    def prepare(self) -> None:
        """Create the enrichment tables and views, or refuse a store whose tables drifted.

        Once per writable open, before any read: `check_shape` runs ahead of the DDL because
        `CREATE TABLE IF NOT EXISTS` would leave a drifted table alone, to fail at the first
        read. A read-only handle skips this and reads whatever a pass left.
        """
        check_shape(self.connection, _SCHEMA)
        self.connection.execute(_SCHEMA)

    # --- what a page reads -------------------------------------------------------------------

    def held(self) -> bool:
        """Whether the store holds every enrichment table — a pass creates them, not the
        exporter, and a read-only handle cannot, so a page asks before `described` or `line`."""
        catalog = "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'main'"
        tables = {name for (name,) in self.store._rows(catalog, {}).rows}
        return {rows.table for rows in ROWS.values()} <= tables

    def described(self, *, session_id: str, source: str, widths: Mapping[str, int]) -> Described:
        """What a pass wrote about one session, one thread's turns and the session's runs, cut.

        `source` is the thread whose turns are wanted: `main` on a session page, the run's id
        on a run page. A session no pass reached is an empty answer, cited — the statement ran.
        """
        bindings = library.bind(ENRICHMENT, widths, {}, session_id=session_id, source=source)
        rows = [
            DescribedItem(**row)
            for row in library.fetch(self.store, library.load(ENRICHMENT), bindings)
        ]
        return Described(rows, Citation(ENRICHMENT, bindings))

    def line(self, level: Level, field: str, keys: Mapping[str, str]) -> WholeValue | None:
        """One line a pass wrote about one item, whole: its `description` or its `friction`.

        `keys` are the level's own primary key by column name, which is what the fetch route
        carries; a key the level's statement does not bind is refused by name. None where no
        pass wrote a row under those keys.
        """
        name = LINE_STATEMENTS[level, field]
        bindings = library.bind(name, {}, {}, **keys)
        row = library.one(self.store, name, bindings)
        return None if row is None else WholeValue(citation=Citation(name, bindings), **row)

    # --- what a pass reads: the items, built by `store/items.py` ----------------------------

    def items(self, level: Level, project: str | None = None) -> list[Item]:
        """Every enrichable item of one level. The enricher's one door into the store.

        `turn_items`, `run_items` and `session_items` are public because the tests read one
        level directly.
        """
        return ItemReader(self.connection).items(level, project)

    def turn_items(self, project: str | None = None) -> list[TurnItem]:
        return ItemReader(self.connection).turn_items(project)

    def run_items(self, project: str | None = None) -> list[AgentRunItem]:
        return ItemReader(self.connection).run_items(project)

    def session_items(self, project: str | None = None) -> list[SessionItem]:
        return ItemReader(self.connection).session_items(project)

    def item_parents(self, project: str | None = None) -> dict[str, str | None]:
        """Each item's key against the key of the item whose prompt embeds its description."""
        return ItemReader(self.connection).item_parents(project)

    def stamps(self, level: Level) -> dict[str, Stamp]:
        """What every row of one level was written under, keyed by item key.

        Read again after every round rather than cached: a child's new description changes
        its parents' rendered input, and only a fresh read sees that. What the caller does
        with them is `enrich/stamp.py:stale`.
        """
        rows = ROWS[level]
        columns = ", ".join((*rows.keys, *STAMP_COLUMNS))
        held = self.connection.execute(f"SELECT {columns} FROM {rows.table}").fetchall()
        width = len(rows.keys)
        return {item_key(level, *row[:width]): Stamp(*row[width:]) for row in held}

    def upsert(self, item: Item, enrichment: Enrichment, stamp: Stamp) -> None:
        """Write one item's enrichment, replacing whatever the key held before."""
        rows = ROWS[item.level]
        columns = ", ".join((*rows.keys, *PAYLOAD_COLUMNS))
        placeholders = ", ".join("?" for _ in range(len(rows.keys) + len(PAYLOAD_COLUMNS)))
        self.connection.execute(
            f"INSERT OR REPLACE INTO {rows.table} ({columns}) VALUES ({placeholders})",
            [
                *item.key_values,
                # Field order, both dataclasses, because that is where `PAYLOAD_COLUMNS` gets
                # its names: a value list spelled by hand could drift from the column list
                # beside it. The two closed vocabularies are `StrEnum` members, so DuckDB
                # binds them as the strings the taxonomy spells.
                *astuple(enrichment),
                *astuple(stamp),
                dt.datetime.now(dt.UTC),
            ],
        )

    def sweep_zombies(self) -> int:
        """Delete enrichments whose base row is gone, and say how many there were.

        An extractor bump can redraw turn boundaries or drop a run, and the LEFT-joined
        views hide the leftovers completely — nothing else in the system would report them.
        """
        swept = 0
        for rows in ROWS.values():
            match = " AND ".join(
                f"b.{base} = e.{key}" for base, key in zip(rows.base_keys, rows.keys, strict=True)
            )
            deleted = self.connection.execute(
                f"DELETE FROM {rows.table} e"
                f" WHERE NOT EXISTS (SELECT 1 FROM {rows.base} b WHERE {match})"
            ).fetchone()
            swept += deleted[0] if deleted else 0
        return swept
