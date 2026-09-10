"""Where `hp` keeps its archive when no `--db` names one.

Both the environment and `Path.home` are monkeypatched here, so the leaves name the whole
path hyphae builds — the dotdir and the file under it — without writing to a real home.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from hyphae.export.duckdb import DuckDbExporter
from hyphae.store_path import HP_DB, default_store
from tests.conftest import NO_WAIT, TraceFactory, stored_rows

SPINE = "4208c1bd-78a0-46ef-9d3c-269b9b7a8e2b"


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch) -> Callable[[Path], None]:
    """Put a directory of the test's choosing where the home directory would be."""

    def stub(root: Path) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda _cls: root))

    return stub


@pytest.fixture
def no_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make consulting the home directory a failure, for the leaves that must not reach it."""

    def refuse(_cls: type[Path]) -> Path:
        raise AssertionError("asked for the home directory")

    monkeypatch.setattr(Path, "home", classmethod(refuse))


@pytest.mark.usefixtures("no_home")
def test_the_environment_names_the_store_outright(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`HP_DB` is the whole path to the store, not a directory to hang a file name under."""
    # If the environment names a store...
    store = tmp_path / "elsewhere.duckdb"
    monkeypatch.setenv(HP_DB, str(store))
    # ...that is the path, joined to nothing — and the home directory is never consulted.
    assert default_store() == store


def test_a_store_nothing_names_lives_in_the_home_dotdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home: Callable[[Path], None]
) -> None:
    """With no `HP_DB`, the archive is `~/.hyphae/traces.duckdb` — one store per person,
    outside every checkout, where a person looks for it.

    The literal path is the assertion: a drifting dotdir or file name would move every
    reader's archive with nothing to say where it went.
    """
    # If nothing in the environment names a store...
    monkeypatch.delenv(HP_DB, raising=False)
    home(tmp_path)
    # ...the store is the one file in the one dotdir under the home directory.
    assert default_store() == tmp_path / ".hyphae" / "traces.duckdb"


@pytest.mark.usefixtures("no_home")
@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_hp_db_refuses_rather_than_falling_back(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """`HP_DB` set to nothing is a broken environment, and it says so rather than quietly
    archiving somewhere else.

    An exported-but-empty variable is what an unset shell variable expands to, so falling
    back would write a caller's sessions into a store they did not ask for and cannot find.
    """
    monkeypatch.setenv(HP_DB, value)
    with pytest.raises(SystemExit, match=HP_DB):
        default_store()


def test_naming_the_store_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home: Callable[[Path], None]
) -> None:
    """Resolving the default store touches no disk: reading `--help` leaves no directory
    behind, and only a write creates one."""
    monkeypatch.delenv(HP_DB, raising=False)
    # If the dotdir does not exist yet...
    root = tmp_path / "never-created"
    home(root)
    # ...then naming the store neither creates it nor the file under it.
    assert default_store() == root / ".hyphae" / "traces.duckdb"
    assert not root.exists()


def test_the_first_write_creates_the_directories_above_the_store(
    tmp_path: Path, fixture_trace: TraceFactory
) -> None:
    """An extract into a store path whose directories do not exist yet makes them.

    This is what lets the per-user default work on a machine that has never run `hp`: the
    dotdir under the home directory does not exist until something writes to it.
    """
    # If a session is exported into a store nested under directories nothing created...
    store = tmp_path / "home" / ".hyphae" / "traces.duckdb"
    exporter = DuckDbExporter(store, wait=NO_WAIT)
    exporter.export(fixture_trace("spine", SPINE), "planted")
    # ...the directories are made on the way, and the session reads back out of the store.
    assert stored_rows(store, "SELECT id FROM sessions") == [(SPINE,)]
