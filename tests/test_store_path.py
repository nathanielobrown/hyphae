"""Where `hp` keeps its archive when no `--db` names one.

Both the environment and `platformdirs` are monkeypatched here. What these leaves prove is
that hyphae asks the library for `hyphae`'s data directory and joins one file name onto it;
what that directory resolves to on this OS is the library's contract, tested by the library.
"""

from collections.abc import Callable
from pathlib import Path

import platformdirs
import pytest

from hyphae.export.duckdb import DuckDbExporter
from hyphae.store_path import HP_DB, default_store
from tests.conftest import NO_WAIT, TraceFactory, stored_rows

SPINE = "4208c1bd-78a0-46ef-9d3c-269b9b7a8e2b"

# What a data directory the test names looks like, so a leaf comparing a whole path reads.
APP = "hyphae"


@pytest.fixture
def data_dir(monkeypatch: pytest.MonkeyPatch) -> Callable[[Path], list[str]]:
    """Put a directory of the test's choosing where `platformdirs` would name the real one.

    Hands back the list of app names hyphae asked for, so a leaf can hold the one argument
    that decides the directory — a drifting app name would otherwise move every reader's
    archive silently.
    """

    def stub(root: Path) -> list[str]:
        asked: list[str] = []

        def user_data_path(appname: str) -> Path:
            asked.append(appname)
            return root

        monkeypatch.setattr(platformdirs, "user_data_path", user_data_path)
        return asked

    return stub


@pytest.fixture
def no_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make consulting `platformdirs` a failure, for the leaves that must not reach it."""

    def refuse(appname: str) -> Path:
        raise AssertionError(f"asked platformdirs for {appname}'s data directory")

    monkeypatch.setattr(platformdirs, "user_data_path", refuse)


@pytest.mark.usefixtures("no_data_dir")
def test_the_environment_names_the_store_outright(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`HP_DB` is the whole path to the store, not a directory to hang a file name under."""
    # If the environment names a store...
    store = tmp_path / "elsewhere.duckdb"
    monkeypatch.setenv(HP_DB, str(store))
    # ...that is the path, joined to nothing — and the data directory is never consulted.
    assert default_store() == store


def test_a_store_nothing_names_lives_in_the_user_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data_dir: Callable[[Path], list[str]]
) -> None:
    """With no `HP_DB`, the archive is `traces.duckdb` in the data directory this OS gives
    `hyphae` — one store per person, outside every checkout."""
    # If nothing in the environment names a store...
    monkeypatch.delenv(HP_DB, raising=False)
    asked = data_dir(tmp_path)
    # ...the store is the one file in the directory the library names...
    assert default_store() == tmp_path / "traces.duckdb"
    # ...and the name it was asked under is the project's, once: an app name that drifted
    # would move every reader's archive with nothing to say where it went.
    assert asked == [APP]


@pytest.mark.usefixtures("no_data_dir")
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data_dir: Callable[[Path], list[str]]
) -> None:
    """Resolving the default store touches no disk: reading `--help` leaves no directory
    behind, and only a write creates one."""
    monkeypatch.delenv(HP_DB, raising=False)
    # If the data directory does not exist yet...
    root = tmp_path / "never-created"
    data_dir(root)
    # ...then naming the store neither creates it nor the file under it.
    assert default_store() == root / "traces.duckdb"
    assert not root.exists()


def test_the_first_write_creates_the_directories_above_the_store(
    tmp_path: Path, fixture_trace: TraceFactory
) -> None:
    """An extract into a store path whose directories do not exist yet makes them.

    This is what lets the per-user default work on a machine that has never run `hp`: the
    data directory the OS names for `hyphae` does not exist until something writes to it.
    """
    # If a session is exported into a store nested under directories nothing created...
    store = tmp_path / "Application Support" / "hyphae" / "traces.duckdb"
    exporter = DuckDbExporter(store, wait=NO_WAIT)
    exporter.export(fixture_trace("spine", SPINE), "planted")
    # ...the directories are made on the way, and the session reads back out of the store.
    assert stored_rows(store, "SELECT id FROM sessions") == [(SPINE,)]
