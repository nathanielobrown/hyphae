"""`OffloadRepository`: one chunk of a tool result Claude Code wrote to a file, as a model.

Driven against the corpus store, over the seam the offload page reads through: the row
reaches its model unchanged under the strict build, a chunk is cut at the offset asked for,
a name the session never offloaded is `None`, the method binds exactly what its statement
declares, and it hands back the citation a footer prints. The file is the corpus's one
recorded offload (`tests/conftest.py:OFFLOAD_FILE`, 159 characters), chunked at 64 so a
boundary is a real overflow of a recorded value rather than a staged one.

The `HYPHAE_LIVE_STORE` leaf at the end is the backstop over real shapes, as in
`tests/store/test_sessions.py`: off by default, run by hand before a PR touching a model opens.
"""

import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation
from hyphae.models.record import Offload
from hyphae.store import library, offloads
from hyphae.store.handle import Store, open_store
from hyphae.store.offloads import OffloadRepository
from hyphae.store.trace_store import StoreExporter
from tests.conftest import CONFIG_ONLY, NO_WAIT, OFFLOAD_CHARS, OFFLOAD_FILE
from tests.store.test_sessions import LIVE_STORE, rows_of

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")

# The chunk the leaves cut the recorded file at: three chunks over 159 characters.
CHUNK = 64


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> OffloadRepository:
    return store.offloads


def recorded(repository: OffloadRepository, after: int) -> Offload | None:
    """The corpus's one offload file, chunked at `CHUNK` from `after`."""
    return repository.chunk(session_id=CONFIG_ONLY, name=OFFLOAD_FILE, after=after, size=CHUNK)


def test_the_handle_hands_out_one_repository(store: Store) -> None:
    """`store.offloads` is the repository over that store, built once."""
    assert store.offloads is store.offloads
    assert isinstance(store.offloads, OffloadRepository)
    assert store.offloads.store is store


# --- row to model ---------------------------------------------------------------------------


def test_an_offload_row_reaches_its_model_unchanged(
    store: Store, repository: OffloadRepository
) -> None:
    """A chunk is the statement's one row as a strict model, carrying its citation."""
    chunk = recorded(repository, 0)
    bindings = library.bind(
        offloads.OFFLOAD,
        {},
        {},
        session_id=CONFIG_ONLY,
        name=OFFLOAD_FILE,
        after_chars=0,
        chunk_chars=CHUNK,
    )
    (raw,) = rows_of(store, library.load(offloads.OFFLOAD), bindings)
    assert chunk is not None
    assert asdict(chunk) == {**raw, "citation": Citation(offloads.OFFLOAD, bindings)}


# --- the values ------------------------------------------------------------------------------


def test_the_recorded_file_is_served_in_chunks_that_reassemble_it(
    store: Store, repository: OffloadRepository
) -> None:
    """Chunk by chunk from the start, the file comes back once and in order, each chunk cut
    at its own offset — and the model says what was on disk beside what was decoded."""
    (stored,) = rows_of(
        store,
        "SELECT content FROM offload_files WHERE session_id = $session_id AND name = $name",
        {"session_id": CONFIG_ONLY, "name": OFFLOAD_FILE},
    )
    content = stored["content"]
    assert len(content) == OFFLOAD_CHARS, "the recorded offload moved: re-pick the file"
    chunks = [recorded(repository, after) for after in (0, CHUNK, 2 * CHUNK)]
    assert [chunk.chunk for chunk in chunks if chunk] == [
        content[:CHUNK],
        content[CHUNK : 2 * CHUNK],
        content[2 * CHUNK :],
    ]
    # Every chunk carries the file's facts whole: the name, the bytes on disk (two more than
    # the characters, for the one multibyte character the file holds), and a clean decode.
    assert {
        (chunk.name, chunk.size_bytes, chunk.content_chars, chunk.lossy_decode)
        for chunk in chunks
        if chunk
    } == {(OFFLOAD_FILE, 161, OFFLOAD_CHARS, False)}
    # ...and the last one cites the offset it was cut at, not the file's start.
    assert chunks[2] is not None
    assert chunks[2].citation == Citation(
        offloads.OFFLOAD,
        {
            "session_id": CONFIG_ONLY,
            "name": OFFLOAD_FILE,
            "after_chars": 2 * CHUNK,
            "chunk_chars": CHUNK,
        },
    )


def test_an_offset_past_the_end_is_the_file_with_nothing_left(
    repository: OffloadRepository,
) -> None:
    """The row is the file's, so it is still there past its end: an empty chunk, not `None`.
    The page turns that into "no next chunk"; `None` is for a file the session never had."""
    past = recorded(repository, OFFLOAD_CHARS)
    assert past is not None
    assert (past.chunk, past.content_chars) == ("", OFFLOAD_CHARS)


@pytest.mark.parametrize(
    ("session_id", "name"),
    [(CONFIG_ONLY, "not-a-file.txt"), ("not-a-session", OFFLOAD_FILE), (CONFIG_ONLY, "")],
    ids=["unknown file", "unknown session", "empty name"],
)
def test_a_file_the_session_never_offloaded_is_none(
    repository: OffloadRepository, session_id: str, name: str
) -> None:
    """None, which the page turns into its 404 — never a model over no row."""
    assert repository.chunk(session_id=session_id, name=name, after=0, size=CHUNK) is None


def test_a_store_nothing_was_extracted_into_has_no_file(tmp_path: Path) -> None:
    """A store with the schema and no sessions answers `None`, and refuses nothing."""
    db = tmp_path / "traces.duckdb"
    StoreExporter(db, wait=NO_WAIT)
    with open_store(db, read_only=True, wait=NO_WAIT) as store:
        assert recorded(store.offloads, 0) is None


# --- refusals --------------------------------------------------------------------------------

# The one method, with one whole call, so a keyword can be dropped from it or added to it.
CALL: dict[str, Any] = {
    "session_id": CONFIG_ONLY,
    "name": OFFLOAD_FILE,
    "after": 0,
    "size": CHUNK,
}


def test_a_keyword_left_off_or_added_is_refused(repository: OffloadRepository) -> None:
    """The method binds exactly what its statement declares, keyword by keyword: a drifted
    signature fails here before any page runs."""
    # Untyped, so the checker lets a call drift the way a page's could.
    chunk: Callable[..., Any] = repository.chunk
    # The whole call runs...
    chunk(**CALL)
    # ...one keyword short, it does not...
    with pytest.raises(TypeError, match="missing"):
        chunk(**{key: value for key, value in CALL.items() if key != "after"})
    # ...nor with one it never named: the statement prints at no width, so there is none to pass...
    with pytest.raises(TypeError, match="unexpected keyword"):
        chunk(**CALL, widths={})
    # ...nor positionally: the keywords are the contract.
    with pytest.raises(TypeError, match="positional"):
        chunk(*CALL.values())


# --- the backstop over real shapes -----------------------------------------------------------


@pytest.mark.skipif(
    LIVE_STORE not in os.environ, reason=f"set {LIVE_STORE} to a real trace store to run"
)
def test_every_file_of_the_real_archive_builds_its_model(tmp_path: Path) -> None:
    """The first chunk of every offload file the archive holds, under the strict build.

    Counts only: a chunk is session content, and a failing assertion prints its operands. The
    archive is copied first, with its write-ahead log: a reader holding the archive open
    blocks the extract that writes it.
    """
    archive = Path(os.environ[LIVE_STORE])
    copy = tmp_path / archive.name
    shutil.copy(archive, copy)
    wal = archive.with_name(f"{archive.name}.wal")
    if wal.exists():
        shutil.copy(wal, copy.with_name(f"{copy.name}.wal"))
    with open_store(copy, read_only=True, wait=NO_WAIT) as store:
        files = rows_of(store, "SELECT session_id, name FROM offload_files", {})
        built = [
            store.offloads.chunk(
                session_id=one["session_id"], name=one["name"], after=0, size=CHUNK
            )
            for one in files
        ]
    assert files, "the archive holds no offload file, so this leaf proved nothing"
    assert all(chunk is not None and len(chunk.chunk) <= CHUNK for chunk in built)
    assert len(built) == len(files)
