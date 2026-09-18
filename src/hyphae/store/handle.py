"""One open trace store, and the one verb a page or `hp query` runs SQL through.

The driver stays inside this package: a page or a query holds a `Store` rather than a
connection, and the forbidden contract holds every package outside the store to that
(`docs/layering.md`). The enrichment tables keep their own writer in this package until PR
4.5 of the store-layering plan hangs it off the handle; the OTLP ledger's stays a writer of
its own. `rows` hands back columns and tuples because its two consumers want different shapes
from them — the page reads want dicts, the runner a header and a body — and a cursor is the
driver's type.
"""

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NamedTuple

import duckdb

from hyphae.models.citation import ParamValue
from hyphae.store import macros
from hyphae.store.trace_store import open_trace_store


class Fetched(NamedTuple):
    """What one statement answered: the column names DuckDB reported, and the rows as tuples."""

    columns: tuple[str, ...]
    rows: list[tuple[Any, ...]]


class Store:
    """One open trace store, for as long as the caller holds it.

    A page gets one per request (`PAGE_WAIT`); a query gets one per run (`CLI_WAIT`). The
    repositories block below fills in as each phase-4 PR hangs its area off the handle.
    `connection` is public until the last `rows` caller outside this package is gone.
    """

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    # The repositories, one `cached_property` per area as each phase-4 PR lands it, with a
    # blank line between neighbours so two PRs' edits rebase past each other
    # (`plans/store-layering/phase-4-repositories.md`).

    # sessions and projects

    # records and offload

    # failures

    # analysis

    # enrichment

    # nodes

    # the NavTree and the walk

    def rows(self, sql: str, bindings: Mapping[str, ParamValue]) -> Fetched:
        """Run one statement with every value bound by name, and hand back what it answered.

        DDL runs through here too — the runner's corpus relations are temp tables — and
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
