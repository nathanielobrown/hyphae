"""One open trace store, and the one verb a page or `hp query` runs SQL through.

The driver stays inside this package: a page or a query holds a `Store` rather than a
connection, and the forbidden contract holds every package outside the store to that
(`docs/layering.md`). The enrichment tables' writer is the `enrichment` repository, prepared
on a writable handle by the pass that owns it; the OTLP ledger's stays a writer of its own.
`rows` hands back columns and tuples because its two consumers want different shapes from
them — the page reads want dicts, `hp query` a header and a body — and a cursor is the
driver's type.
"""

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import Any, NamedTuple

import duckdb

from hyphae.models.citation import ParamValue
from hyphae.store import macros
from hyphae.store.analysis import AnalysisRepository
from hyphae.store.enrichment import EnrichmentRepository
from hyphae.store.failures import FailureRepository
from hyphae.store.nav import NavRepository
from hyphae.store.nodes import NodeRepository
from hyphae.store.offloads import OffloadRepository
from hyphae.store.records import RecordRepository
from hyphae.store.sessions import SessionRepository
from hyphae.store.trace_store import open_trace_store


class Fetched(NamedTuple):
    """What one statement answered: the column names DuckDB reported, and the rows as tuples."""

    columns: tuple[str, ...]
    rows: list[tuple[Any, ...]]


class Store:
    """One open trace store, for as long as the caller holds it.

    A page gets one per request (`PAGE_WAIT`); a query gets one per run (`CLI_WAIT`). Every
    area's repository hangs off it as a property below, and a page names the repository it
    reads. `connection` is public until the last `rows` caller outside this package is gone.
    """

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    # The repositories, one `cached_property` per area.

    @cached_property
    def sessions(self) -> SessionRepository:
        """The sessions and the projects: the list, the landing page, one session's header."""
        return SessionRepository(self)

    @cached_property
    def records(self) -> RecordRepository:
        """The records browser: one page of a thread's raw transcript, at a keyset cursor."""
        return RecordRepository(self)

    @cached_property
    def offloads(self) -> OffloadRepository:
        """The offload page: one chunk of a tool result Claude Code wrote to a file."""
        return OffloadRepository(self)

    @cached_property
    def failures(self) -> FailureRepository:
        """The errors page and the error stepper: every failed tool call of one session."""
        return FailureRepository(self)

    @cached_property
    def analysis(self) -> AnalysisRepository:
        """`hp query`: the corpus scoped to one project, and any library statement run over it."""
        return AnalysisRepository(self)

    @cached_property
    def enrichment(self) -> EnrichmentRepository:
        """What a pass wrote about each item, and the pass's own reads and writes: a page asks
        `held` before `described` or `line`; a pass prepares a writable handle first."""
        return EnrichmentRepository(self)

    @cached_property
    def nodes(self) -> NodeRepository:
        """The node page: one node's header whole, and one of its fat values whole."""
        return NodeRepository(self)

    @cached_property
    def nav(self) -> NavRepository:
        """The NavTree: one level whole, and every agent run of the session."""
        return NavRepository(self)

    def rows(self, sql: str, bindings: Mapping[str, ParamValue]) -> Fetched:
        """Run one statement with every value bound by name, and hand back what it answered.

        DDL runs through here too — the analysis corpus relations are temp tables — and
        answers whatever the driver reports for it. A binding the statement names and the
        caller left out is the driver's own error, not a NULL bound in its place.
        """
        cursor = self.connection.execute(sql, dict(bindings))
        columns = tuple(column[0] for column in cursor.description or ())
        return Fetched(columns, cursor.fetchall())


@contextmanager
def open_store(path: Path, *, read_only: bool, wait: float) -> Generator[Store]:
    """`open_trace_store` with the macros installed, handing back a `Store`. Raises what it raises.

    The library's shared SQL functions are installed on every store opened here, so a
    statement that calls one by name runs under every consumer alike.
    """
    with open_trace_store(path, read_only=read_only, wait=wait) as connection:
        macros.install(connection)
        yield Store(connection)
