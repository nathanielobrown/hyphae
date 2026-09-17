"""The delivery ledger on its own: the store's table, driven without an exporter.

The exporter's leaves in `tests/export/test_otlp__delivery.py` drive the ledger under the one
`MAPPER_VERSION`, so they cannot tell a keyword the caller passes from one the ledger fills
in. This file varies it.
"""

from pathlib import Path

import pytest

from hyphae.store.delivery import DeliveryLedger
from hyphae.store.trace_store import DuckDbExporter, open_trace_store
from tests.conftest import NO_WAIT


def test_the_ledger_reads_back_only_the_mapper_version_it_recorded_under(tmp_path: Path) -> None:
    """A ledger has no mapper version of its own: the caller names one at every read and write."""
    db = tmp_path / "traces.duckdb"
    DuckDbExporter(db, wait=NO_WAIT)
    with open_trace_store(db, read_only=False, wait=NO_WAIT) as connection:
        ledger = DeliveryLedger(connection, backend="generic")
        ledger.create()
        # If a delivery is recorded under one mapper version...
        ledger.record("session-1", "fingerprint-1", 3, mapper_version="a")
        # ...then a read under that version holds it, and a read under another does not: the
        # rows a shaping change left behind are what makes it re-send the corpus.
        assert ledger.fingerprints(mapper_version="a") == {"session-1": "fingerprint-1"}
        assert ledger.fingerprints(mapper_version="b") == {}
        # And neither side may leave the version to the ledger.
        with pytest.raises(TypeError):
            ledger.fingerprints()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            ledger.record("session-1", "fingerprint-1", 3)  # type: ignore[call-arg]
