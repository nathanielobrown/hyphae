"""The settings file: what `hp` remembers for a person between runs."""

import json
import os
from pathlib import Path

import pytest

from hyphae import user_settings
from hyphae.store_path import HP_DB
from tests.conftest import PINNED_DB

REMEMBERED = {"extract": {"projects": ["-Users-nob-repos-mycelia", "-Users-nob-repos-hyphae"]}}


def test_a_written_mapping_reads_back_equal(tmp_path: Path) -> None:
    """What one run writes, the next reads: a list of names, or the word for everything."""
    path = tmp_path / "settings.json"
    user_settings.write(REMEMBERED, path)
    assert user_settings.read(path) == REMEMBERED
    # The "all" choice is a string where the list would be, and comes back as that string.
    user_settings.write({"extract": {"projects": "all"}}, path)
    assert user_settings.read(path) == {"extract": {"projects": "all"}}


def test_a_missing_file_reads_as_nothing_remembered(tmp_path: Path) -> None:
    """A fresh machine has no settings file, and that is an empty mapping rather than an error."""
    assert user_settings.read(tmp_path / "none.json") == {}


def test_a_malformed_file_crashes_rather_than_reading_as_empty(tmp_path: Path) -> None:
    """A settings file that is not JSON is a file to look at, not a preference to forget."""
    path = tmp_path / "settings.json"
    path.write_text("{not json")  # invented
    with pytest.raises(json.JSONDecodeError):
        user_settings.read(path)


def test_write_creates_the_directory_above_the_file(tmp_path: Path) -> None:
    """The first write on a machine makes the dotdir the file lives in."""
    path = tmp_path / "a" / "b" / "settings.json"
    user_settings.write(REMEMBERED, path)
    assert path.is_file()


def test_the_default_path_is_under_home_not_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The file lives at `~/.hyphae/settings.json`, wherever `HP_DB` points the store."""
    # If HOME is moved while the store is still pinned elsewhere (the suite pins it)...
    monkeypatch.setenv("HOME", str(tmp_path))
    assert os.environ[HP_DB] == str(PINNED_DB)
    # ...then a write with no path lands under HOME's dotdir, and a read with none finds it.
    user_settings.write(REMEMBERED)
    assert (tmp_path / ".hyphae" / "settings.json").is_file()
    assert user_settings.read() == REMEMBERED
