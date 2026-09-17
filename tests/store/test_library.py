"""The query library as a registry: what it lists, what a citation ends at, what it sizes.

The statements themselves are weighed where their consumers are — `tests/analyze` runs them
through `hp query` and `tests/view` through the pages. This module holds what the library
says about itself without running anything.
"""

from pathlib import Path

import pytest

from hyphae.store import library

# The values the library's own comments give the reasons for. `tests/analyze` binds these by
# name, so a drifted number would pass there and change a report's rows or a page's cut
# silently; `docs/viewer-bounds.md` prints the children log's 300. Pinned the way
# `tests/view/test_bounds.py` pins the surfaces' widths.
SIZES = {
    "RAW_CHARS": 2000,
    "ERROR_CHARS": 200,
    "SIGNATURE_CHARS": 120,
    "COMMAND_HEAD_CHARS": 60,
    "LOG_CHARS": 300,
    "WINDOW_DAYS": 28,
}


def test_names_lists_every_file_in_the_directory_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The directory is the registry: a `.sql` stem is a name, and nothing else in it is."""
    # What ships: one name per file, sorted, and every name is a file the loader can read.
    shipped = library.names()
    assert shipped == sorted(path.stem for path in library.QUERY_DIR.glob("*.sql"))
    assert all(library.load(name) for name in shipped)
    # A directory the test owns says what counts: a planted statement is listed, a stray
    # file beside it is not, whatever its name.
    (tmp_path / "planted.sql").write_text("SELECT 1")
    (tmp_path / "notes.txt").write_text("not a query")
    (tmp_path / "sessions.md").write_text("not one either")
    monkeypatch.setattr(library, "QUERY_DIR", tmp_path)
    assert library.names() == ["planted"]


def test_a_citation_with_nothing_bound_ends_at_the_query_file() -> None:
    """A citation is a line someone pastes into a report, so it never trails whitespace."""
    # Every shipped query resolves at least one binding, so this is the contract for a caller
    # that composes its own — the viewer builds citations from what it bound, not a manifest.
    assert library.citation("sessions", {}) == "-- queries/sessions.sql"


@pytest.mark.parametrize(("name", "value"), sorted(SIZES.items()))
def test_a_size_the_library_declares_is_the_documented_one(name: str, value: int) -> None:
    """A number a report or a page is cut at holds still until someone changes it on purpose."""
    assert getattr(library, name) == value
