"""The OTLP delivery ledger: what each backend acknowledged of each session.

One table, `otlp_delivery`, created on the first send rather than by the schema, so a store
that never shipped holds no ledger and a read-only opener can still ask it what was
delivered. The exporter that writes it is `hyphae.export.otlp_delivery`, which passes the
mapper version it ships under at every read and write; the ledger holds no version of its own.
"""

import datetime as dt

import duckdb

from hyphae.store.schema import check_shape

# Lives in the trace store beside the fingerprints it compares against, created on first
# export like the enrichment tables — table existence, no schema-version bump. Deliberately
# outside `TABLES`: swept into the replace transaction it would be erased by every
# re-extract, and every later run would ship the corpus again as duplicates.
_DELIVERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS otlp_delivery (
    session_id VARCHAR NOT NULL,
    backend VARCHAR NOT NULL,
    -- The `extract_state` fingerprint that was shipped, and the mapper that shaped it.
    -- Either one moving makes the session undelivered again.
    fingerprint VARCHAR NOT NULL,
    mapper_version VARCHAR NOT NULL,
    -- The local manifest: what a future `--verify` counts against the backend.
    spans_sent BIGINT NOT NULL,
    delivered_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (session_id, backend)
);
"""


class DeliveryLedger:
    """What one backend acknowledged per session, and the fingerprints a send diffs against.

    Reading is safe over a store opened read-only: a store that never shipped holds no
    ledger table, and the ledger answers for it rather than creating one. Only `create()`
    writes, and only `OtlpExporter` calls it — which is what lets the census read the same
    ledger a send writes without the write lock.

    Takes an open connection rather than a path because DuckDB admits one writer at a time:
    the `StoreExtractor` reading beside it has to be holding the same one.
    """

    def __init__(self, connection: duckdb.DuckDBPyConnection, *, backend: str) -> None:
        self.connection = connection
        # The backend's name is the whole address here: a ledger never sees a key.
        self.backend = backend

    def create(self) -> None:
        """Make the store hold the ledger table, refusing one whose columns have drifted."""
        # Before the DDL, like every other owner of a table in this package: a ledger that
        # drifted from the DDL is skipped by `CREATE TABLE IF NOT EXISTS` and fails later.
        check_shape(self.connection, _DELIVERY_SCHEMA)
        self.connection.execute(_DELIVERY_SCHEMA)

    def fingerprints(self, *, mapper_version: str) -> dict[str, str]:
        """What this backend holds, as far as delivery can tell.

        Rows recorded under a mapper other than `mapper_version` are left out, which is what
        makes a shaping change re-send the corpus: `refresh()` sees them as sessions it never
        shipped. No default: the ledger has no version of its own, and the caller that
        records under one must read under the same.
        """
        if not self._exists():
            return {}
        rows = self.connection.execute(
            "SELECT session_id, fingerprint FROM otlp_delivery"
            " WHERE backend = ? AND mapper_version = ?",
            [self.backend, mapper_version],
        ).fetchall()
        return dict(rows)

    def record(
        self, session_id: str, fingerprint: str, spans_sent: int, *, mapper_version: str
    ) -> None:
        """Record one confirmed delivery, replacing what this backend held for the session."""
        self.connection.execute(
            "INSERT OR REPLACE INTO otlp_delivery VALUES (?, ?, ?, ?, ?, ?)",
            [
                session_id,
                self.backend,
                fingerprint,
                mapper_version,
                spans_sent,
                dt.datetime.now(dt.UTC),
            ],
        )

    def _exists(self) -> bool:
        """Whether the store holds the ledger yet. A store that never shipped does not, and
        a reader must not be the one to change that."""
        return self.connection.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE table_name = 'otlp_delivery'"
        ).fetchone() != (0,)
