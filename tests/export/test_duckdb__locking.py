"""Who holds the trace store's file lock, who queues behind it, and who gives up.

DuckDB admits one process at a time and offers no lock timeout of its own, so every open
here is either waiting or refusing. The holder is always a subprocess: DuckDB answers this
process's own second open differently from the file lock it takes across processes, so an
in-process holder would test the wrong failure (`tests/conftest.locked`).
"""

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from hyphae.export.duckdb import CLI_WAIT, DuckDbExporter, StoreLocked, open_trace_store
from hyphae.export.schema import SchemaVersionError
from hyphae.model import SessionTrace
from tests.conftest import (
    LOCK_TIMEOUT,
    NO_WAIT,
    SPINE,
    TraceFactory,
    locked,
    opens_elsewhere,
    stored_rows,
)
from tests.export.test_duckdb__migrations import foreign_store, unmigratable_store

# How long the holder below keeps the lock before letting go on its own. Every wait the tests
# name is measured against it, and it is what they cost the suite.
BRIEF_HOLD = 0.4
# The budget of a caller that will not queue behind a writer for long.
IMPATIENT = 0.1


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "traces.duckdb"


def stored(db: Path, *traces: SessionTrace) -> None:
    """A store on disk holding these traces — the file the tests below open."""
    exporter = DuckDbExporter(db, wait=NO_WAIT)
    for index, trace in enumerate(traces):
        exporter.export(trace, f"fingerprint-{index}")


def test_a_writer_waits_out_a_holder(db: Path, fixture_trace: TraceFactory):
    """An open that lands during someone else's hold queues behind it instead of failing.

    The collision the wait exists for: `hp extract` and `hp view` on one store. DuckDB has
    no setting for this — `duckdb_settings()` offers `access_mode` and `lock_configuration`
    and nothing else about locks — so the retry is ours.
    """
    stored(db, fixture_trace("spine", SPINE))

    # If another process holds the lock and lets go partway through the block...
    with locked(db, hold=BRIEF_HOLD):
        started = time.monotonic()
        # ...then the open waits for it, and reads the store the holder let go of.
        with open_trace_store(db, read_only=False, wait=LOCK_TIMEOUT) as connection:
            waited = time.monotonic() - started
            assert connection.execute("SELECT count(*) FROM sessions").fetchone() == (1,)
    # It really queued: halved because the holder may have been asleep for up to one of
    # `locked()`'s 50 ms polls before this test's clock started.
    assert waited >= BRIEF_HOLD / 2


def test_a_writer_gives_up_with_a_clear_message(db: Path, fixture_trace: TraceFactory):
    """A caller that outwaits its budget says which store, how long, and who is holding it."""
    stored(db, fixture_trace("spine", SPINE))

    with locked(db) as holder:
        started = time.monotonic()
        with (
            pytest.raises(StoreLocked) as refused,
            open_trace_store(db, read_only=False, wait=IMPATIENT),
        ):
            pass
        waited = time.monotonic() - started

    # The message is the whole of what an operator gets, so it names the file, the budget it
    # spent, and — DuckDB's own line, kept — the process to go and look at.
    message = str(refused.value)
    assert str(db) in message
    assert f"{IMPATIENT:g}" in message
    assert str(holder.pid) in message
    # It gave up on its own budget, not on the holder's: that one is still holding.
    assert waited < 1.0


def refuse_to_sleep(seconds: float) -> None:
    raise AssertionError(f"an open that named no budget slept {seconds}s")


def test_a_zero_wait_open_fails_at_once(
    db: Path, fixture_trace: TraceFactory, monkeypatch: pytest.MonkeyPatch
):
    """A caller that will not wait does not sleep at all — it fails on the first refusal."""
    stored(db, fixture_trace("spine", SPINE))

    # If the store is held and the opener is given no budget...
    with locked(db), monkeypatch.context() as awake:
        awake.setattr(time, "sleep", refuse_to_sleep)
        # ...then it says so straight away rather than polling even once.
        with pytest.raises(StoreLocked), open_trace_store(db, read_only=False, wait=0):
            pass


def test_an_extract_lands_once_an_open_page_lets_go(db: Path, fixture_trace: TraceFactory):
    """An extract started while a viewer page is reading the store writes its session anyway.

    The collision a person meets daily: `hp view` left open on the store `hp extract` writes
    to. What saves it is that the page's read lasts one request — the viewer opens the store
    per request and closes it (`view/deps.py:request_store`) — so the extract queues behind
    one page load rather than behind the viewer's lifetime.
    """
    trace = fixture_trace("spine", SPINE)
    # If the store exists — a page can only read one an extract already wrote...
    stored(db)

    # ...and a page holds it read-only the way `view/store.py:open_store` does, letting go
    # partway through the block...
    with locked(db, hold=BRIEF_HOLD, read_only=True):
        started = time.monotonic()
        # ...then an extract under the CLI's own budget queues behind the read instead of
        # failing on it.
        DuckDbExporter(db, wait=CLI_WAIT).export(trace, "fingerprint-0")
        waited = time.monotonic() - started

    # It really queued: halved because the holder may have been asleep for up to one of
    # `locked()`'s 50 ms polls before this test's clock started.
    assert waited >= BRIEF_HOLD / 2
    # And the session the extract wrote is in the store the page let go of.
    assert stored_rows(db, "SELECT id FROM sessions") == [(trace.session.id,)]


def test_an_extract_gives_up_on_a_page_that_never_lets_go(db: Path, fixture_trace: TraceFactory):
    """An extract that outwaits its budget behind a reader names the process holding the store.

    A read lock shuts a writer out as surely as a write lock does, so the refusal a page
    reading forever earns is the same one another writer earns.
    """
    stored(db, fixture_trace("spine", SPINE))

    # If a reader holds the store for longer than the extract will wait...
    with locked(db, read_only=True) as page:
        # ...then the extract stops rather than hanging, naming the process to go and look at...
        with pytest.raises(StoreLocked) as refused:
            DuckDbExporter(db, wait=IMPATIENT)
        assert str(page.pid) in str(refused.value)

    # ...and the refusal itself left no lock behind: the store opens for write once the page
    # has gone.
    assert opens_elsewhere(db, read_only=False), f"the refusal kept the lock: {refused.value}"


def open_for_write(path: Path) -> object:
    """The opener entered and left the way a caller does — the block is what closes it."""
    with open_trace_store(path, read_only=False, wait=NO_WAIT) as connection:
        return connection


def open_for_export(path: Path) -> object:
    """The exporter's own open, which prepares the store and hands back no connection."""
    return DuckDbExporter(path, wait=NO_WAIT)


@pytest.mark.parametrize(
    "open_store",
    [open_for_export, open_for_write],
    ids=["exporter", "reader"],
)
@pytest.mark.parametrize(
    "write_store", [unmigratable_store, foreign_store], ids=["old-schema", "foreign"]
)
def test_a_refused_store_keeps_none_of_its_lock(
    db: Path,
    write_store: Callable[[Path], dict[str, list[str]]],
    open_store: Callable[[Path], object],
):
    """However a store is opened and whatever makes it unreadable, refusing it frees the file.

    Half the contract is invisible in the file: an opener that raises hands nothing back, so
    no caller is left to close what it opened. The connection lives on in the traceback its
    caller holds, and DuckDB's single-writer lock goes with it — the next process to open the
    store is refused for a reason that has nothing to do with the store.
    """
    # If an unreadable store is refused, and its caller keeps the error to report — a live
    # process, not one exiting on the spot...
    write_store(db)
    with pytest.raises(SchemaVersionError) as refused:
        open_store(db)

    # ...then nothing here still holds the file.
    assert opens_elsewhere(db, read_only=False), f"the refusal kept the write lock: {refused.value}"
