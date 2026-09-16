"""Discovery, skip, and replace — the loop that keeps a DuckDB store level with disk.

Each test builds a projects root the way Claude Code lays one out, filled with copies of
the recorded fixtures, so `refresh()` walks a real directory rather than a stub.
"""

import shutil
import time
from pathlib import Path

import pytest

from hyphae import cli
from hyphae.export.duckdb import DuckDbExporter, StoreLocked
from hyphae.extract import claude_code
from hyphae.extract.claude_code import ClaudeCodeExtractor, ClaudeCodeSource
from hyphae.extract.errors import SessionLayoutError
from hyphae.model import SessionTrace
from hyphae.pipeline import Exporter, ExtractionError, Failure, RefreshResult, refresh
from hyphae.projects import encode_project_path
from tests.conftest import FIXTURES, NO_WAIT, locked, opens_elsewhere, stored_rows
from tests.export.test_duckdb__locking import BRIEF_HOLD, IMPATIENT

SPINE = "4208c1bd-78a0-46ef-9d3c-269b9b7a8e2b"
DUPS = "8ee00a94-b01a-4394-b447-b065f74b11af"
OFFLOAD = "7e37bb35-4dcb-4e16-85be-55ac510c168e"
# The invented session whose assistant record types two fields wrong, so the parser refuses it.
BAD = "invented-wrong-field-type"


class Corpus:
    """A Claude Code projects root on disk, and the project path that addresses it."""

    def __init__(self, root: Path, project: Path) -> None:
        self.root = root
        self.project = project
        self.session_dir = root / encode_project_path(project)
        self.session_dir.mkdir(parents=True)

    def add(self, directory: str, stem: str, *, lines: int | None = None) -> Path:
        """Copy a fixture session in, optionally truncating its transcript to `lines` records.

        The session's own directory comes too, where the fixture has one, so the corpus
        holds subagent transcripts and offloaded results as Claude Code wrote them.
        """
        source = FIXTURES / directory / f"{stem}.jsonl"
        destination = self.session_dir / f"{stem}.jsonl"
        if lines is None:
            shutil.copy(source, destination)
        else:
            kept = source.read_text().split("\n")[:lines]
            destination.write_text("\n".join(kept) + "\n")
        if (FIXTURES / directory / stem).is_dir():
            shutil.copytree(
                FIXTURES / directory / stem, self.session_dir / stem, dirs_exist_ok=True
            )
        return destination

    def extractor(self, **tags: str) -> ClaudeCodeExtractor:
        return ClaudeCodeExtractor(projects_root=self.root, tags=tags)


class CountingExtractor:
    """Wraps an extractor to record which sessions it was asked to parse."""

    def __init__(self, wrapped: ClaudeCodeExtractor) -> None:
        self.wrapped = wrapped
        self.extracted: list[str] = []

    def sessions(self, project: Path) -> list[ClaudeCodeSource]:
        return self.wrapped.sessions(project)

    def extract(self, source: ClaudeCodeSource) -> SessionTrace:
        self.extracted.append(source.id)
        return self.wrapped.extract(source)


class RefusingExtractor:
    """Wraps an extractor to refuse one session with the bare class `refresh` catches.

    Invented on purpose: no recorded session raises the base itself, only a subclass. This is
    the seam that holds the catch to that class rather than to a subclass.
    """

    def __init__(self, wrapped: ClaudeCodeExtractor, refused: str) -> None:
        self.wrapped = wrapped
        self.refused = refused

    def sessions(self, project: Path) -> list[ClaudeCodeSource]:
        return self.wrapped.sessions(project)

    def extract(self, source: ClaudeCodeSource) -> SessionTrace:
        if source.id == self.refused:
            raise ExtractionError("planted")
        return self.wrapped.extract(source)


class ProbingExtractor:
    """Wraps an extractor to ask, before each parse, whether a reader could open the store.

    The question has to come from another process: DuckDB answers this process's own second
    open out of its instance cache, not from the file lock it takes across processes
    (`tests/conftest.opens_elsewhere`).
    """

    def __init__(self, wrapped: ClaudeCodeExtractor, db: Path) -> None:
        self.wrapped = wrapped
        self.db = db
        self.readable: list[bool] = []

    def sessions(self, project: Path) -> list[ClaudeCodeSource]:
        return self.wrapped.sessions(project)

    def extract(self, source: ClaudeCodeSource) -> SessionTrace:
        self.readable.append(self.db.exists() and opens_elsewhere(self.db, read_only=True))
        return self.wrapped.extract(source)


class CountingExporter:
    """Wraps an exporter to record which of its two methods the loop called, in order."""

    def __init__(self, wrapped: Exporter) -> None:
        self.wrapped = wrapped
        self.calls: list[str] = []

    def fingerprints(self) -> dict[str, str]:
        self.calls.append("fingerprints")
        return self.wrapped.fingerprints()

    def export(self, trace: SessionTrace, fingerprint: str) -> None:
        self.calls.append("export")
        self.wrapped.export(trace, fingerprint)


@pytest.fixture
def corpus(tmp_path: Path) -> Corpus:
    project = tmp_path / "repo"
    project.mkdir()
    return Corpus(tmp_path / "projects", project)


@pytest.fixture
def exporter(tmp_path: Path) -> DuckDbExporter:
    return DuckDbExporter(tmp_path / "traces.duckdb", wait=NO_WAIT)


def table(exporter: DuckDbExporter, name: str, session: str) -> list[tuple[object, ...]]:
    key = "id" if name == "sessions" else "session_id"
    return stored_rows(
        exporter.path, f"SELECT * FROM {name} WHERE {key} = ? ORDER BY 1, 2, 3", [session]
    )


def test_a_refresh_ingests_every_session_it_finds(corpus: Corpus, exporter: DuckDbExporter):
    """`refresh()` walks a project's sessions and writes each one into the store."""
    # If a project has two recorded sessions...
    corpus.add("spine", SPINE)
    corpus.add("dup_uuid", DUPS)
    extractor = corpus.extractor()

    result = refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then both are extracted, and each table holds what `extract()` produced for them.
    assert sorted(result.extracted) == sorted([DUPS, SPINE])
    assert result.skipped == []
    for source in extractor.sessions(corpus.project):
        trace = extractor.extract(source)
        assert len(table(exporter, "turns", source.id)) == len(trace.turns)
        assert len(table(exporter, "api_calls", source.id)) == len(trace.api_calls)
        assert len(table(exporter, "raw_records", source.id)) == len(trace.raw_records)


def test_a_tag_reaches_every_session_a_refresh_extracted_and_no_other(
    corpus: Corpus, exporter: DuckDbExporter
):
    """The pairs a caller stamps travel the seam: extractor in, trace across, store out.

    `refresh()` hands the exporter a trace and a fingerprint and nothing else, so the tags
    ride on the trace or they do not arrive. The pairs are invented, and honestly so: a tag
    is the caller's word about a run, and no transcript records one.

    The second half is the trap this seam inherits: a fingerprint covers the session's files,
    which a tag is not part of, so a session the refresh skipped keeps whatever it already
    held (`docs/store.md`).
    """
    # If two sessions are extracted under one pair...
    corpus.add("spine", SPINE)
    corpus.add("dup_uuid", DUPS)
    first = corpus.extractor(batch_id="b1")
    refresh(first.sessions(corpus.project), extractor=first, exporter=exporter)

    # ...then every session that refresh wrote carries it...
    assert stored_rows(exporter.path, "SELECT session_id, key, value FROM session_tags") == sorted(
        [(DUPS, "batch_id", "b1"), (SPINE, "batch_id", "b1")]
    )

    # ...and a second refresh under a different pair re-tags only what it re-extracted, which
    # over untouched files is nothing at all.
    second = corpus.extractor(batch_id="b2")
    result = refresh(second.sessions(corpus.project), extractor=second, exporter=exporter)
    assert result.extracted == []
    assert stored_rows(exporter.path, "SELECT DISTINCT value FROM session_tags") == [("b1",)]


def test_an_unchanged_corpus_is_not_re_extracted(corpus: Corpus, exporter: DuckDbExporter):
    """A second refresh over untouched files parses nothing and rewrites nothing.

    This is what lets the pipeline run on a timer: the cost of a no-op pass is a stat per
    file, not a reparse of the corpus.
    """
    corpus.add("spine", SPINE)
    extractor = CountingExtractor(corpus.extractor())
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)
    stamped = stored_rows(exporter.path, "SELECT extracted_at FROM extract_state")

    # If nothing on disk changed...
    result = refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then the session is skipped, `extract()` ran only on the first pass, and even the
    # row saying when it ran is untouched.
    assert (result.extracted, result.skipped) == ([], [SPINE])
    assert extractor.extracted == [SPINE]
    assert stored_rows(exporter.path, "SELECT extracted_at FROM extract_state") == (stamped)


def test_a_grown_session_is_replaced_rather_than_appended(
    corpus: Corpus, exporter: DuckDbExporter, tmp_path: Path
):
    """Resuming a session and refreshing gives the same rows as extracting it fresh.

    A session grows by appending, and the naive fix — insert only the new lines — leaves
    the session's own metadata frozen at its first extract. Comparing against a store
    built from scratch over the grown file catches that, where a row count would not.
    """
    # If a session was extracted while it was still short...
    corpus.add("spine", SPINE, lines=23)
    extractor = corpus.extractor()
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)
    # Three turns of its own, plus the two its subagent's transcript holds.
    assert len(table(exporter, "turns", SPINE)) == 5

    # ...and then it resumed, growing by thirteen more records...
    corpus.add("spine", SPINE)
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then the store matches one built from scratch over the grown file, table for table.
    fresh = DuckDbExporter(tmp_path / "fresh.duckdb", wait=NO_WAIT)
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=fresh)
    for name in ("sessions", "turns", "api_calls", "raw_records"):
        assert table(exporter, name, SPINE) == table(fresh, name, SPINE)
    assert len(table(exporter, "turns", SPINE)) == 6


def test_a_session_caught_mid_write_heals_on_the_next_refresh(
    corpus: Corpus, exporter: DuckDbExporter
):
    """Extracting a live session keeps the complete records and picks up the rest later.

    Claude Code appends to the transcript of a session that is still running, so a refresh
    on a timer will sooner or later read a line that stops mid-JSON. Refusing the file
    would leave the session unextracted for as long as it stays open.
    """
    # If a refresh catches a transcript with a record only half written...
    transcript = corpus.add("spine", SPINE, lines=22)
    whole = (FIXTURES / "spine" / f"{SPINE}.jsonl").read_text().split("\n")
    transcript.write_text(transcript.read_text() + whole[22][:60])
    extractor = corpus.extractor()
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then the records before it are stored and the half one is not...
    def archived() -> int:
        (row,) = stored_rows(
            exporter.path,
            "SELECT count(*) FROM raw_records WHERE session_id = ? AND source = 'main'",
            [SPINE],
        )
        return row[0]

    assert archived() == 22

    # ...and once Claude Code has finished the line, the next refresh takes the session whole.
    corpus.add("spine", SPINE)
    assert refresh(
        extractor.sessions(corpus.project), extractor=extractor, exporter=exporter
    ).extracted == [SPINE]
    assert archived() == 42


def test_a_session_the_parser_refuses_costs_only_itself(corpus: Corpus, exporter: DuckDbExporter):
    """One unreadable session is reported by name; every other session of the project lands.

    A project is refreshed in one pass, so a record kind or a field the parser cannot read
    used to take down sessions that had nothing wrong with them. The export is per session
    and rolls back on its own, so there is nothing to undo — the loop just keeps going and
    hands the caller what it could not do.
    """
    # If a project holds a session the parser refuses, and it is the first one the loop meets —
    # discovery sorts by id, which decides nothing about a refresh, but what the loop owes its
    # caller is the sessions *after* one that failed...
    corpus.add("invented", BAD)
    corpus.add("spine", SPINE)
    extractor = corpus.extractor()
    sources = sorted(extractor.sessions(corpus.project), key=lambda source: source.id != BAD)

    result = refresh(sources, extractor=extractor, exporter=exporter)

    # ...then the sessions after it are extracted as usual...
    assert result.extracted == [SPINE]
    assert len(table(exporter, "turns", SPINE)) == 6
    # ...the refused one is named with the reason the parser gave...
    assert [failure.session_id for failure in result.failed] == [BAD]
    assert "AssistantRecord" in result.failed[0].error and "line 2" in result.failed[0].error
    # ...and nothing of it reached the store, which is the rollback doing its job.
    assert table(exporter, "raw_records", BAD) == []


def test_an_extractor_refusing_a_session_with_the_base_class_costs_only_that_session(
    corpus: Corpus, exporter: DuckDbExporter
):
    """The loop catches `pipeline.ExtractionError` itself, not one extractor's subclass of it.

    An extractor for another agent will raise its own subclass; what the loop owes it is
    the same treatment a schema error gets. The raise here is planted, since no recorded
    session raises the bare base.
    """
    # If the extractor refuses the first session the loop meets, with the base class alone...
    corpus.add("invented", BAD)
    corpus.add("spine", SPINE)
    extractor = RefusingExtractor(corpus.extractor(), refused=BAD)
    sources = sorted(extractor.sessions(corpus.project), key=lambda source: source.id != BAD)

    result = refresh(sources, extractor=extractor, exporter=exporter)

    # ...then it is named with the reason, and the sessions after it land as usual.
    assert result.failed == [Failure(session_id=BAD, error="planted")]
    assert result.extracted == [SPINE]
    assert len(table(exporter, "turns", SPINE)) == 6


def test_a_session_directory_the_extractor_cannot_read_ends_the_pass(
    corpus: Corpus, exporter: DuckDbExporter
):
    """A layout error is not the class the loop catches: it ends the whole pass, unrecorded.

    A schema error is one session's problem; a file we cannot place is a Claude Code change
    to look at (`extract/errors.py`), and skipping past it would lose whatever it holds.
    """
    # If a session's directory holds a file the extractor cannot place — the invented one
    # `tests/extract/test_claude_code__archive.py` plants...
    corpus.add("spine", SPINE)
    (corpus.session_dir / SPINE / "subagents" / "notes.txt").write_text("")
    extractor = corpus.extractor()

    # ...then the pass stops on it rather than recording it as a failure...
    with pytest.raises(SessionLayoutError, match="unknown file"):
        refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...and nothing of the session reached the store.
    assert table(exporter, "raw_records", SPINE) == []


def test_a_refresh_over_no_sources_reads_the_sink_and_writes_nothing(
    corpus: Corpus, exporter: DuckDbExporter
):
    """Handed nothing to refresh, the loop asks the sink what it holds and stops there."""
    counting = CountingExporter(exporter)

    result = refresh([], extractor=corpus.extractor(), exporter=counting)

    assert result == RefreshResult(extracted=[], skipped=[], failed=[])
    assert counting.calls == ["fingerprints"]


def test_a_new_subagent_file_re_extracts_its_session(corpus: Corpus, exporter: DuckDbExporter):
    """A session whose subagent wrote a transcript is stale, though its own file never changed.

    The fingerprint covers every file under the session directory for exactly this case:
    a subagent, a workflow journal, or an offloaded tool result can all change while the
    main transcript's size and mtime stand still.
    """
    transcript = corpus.add("spine", SPINE)
    extractor = CountingExtractor(corpus.extractor())
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)
    before = exporter.fingerprints()
    unchanged = (transcript.stat().st_size, transcript.stat().st_mtime_ns)

    # If another subagent transcript appears beside an untouched main transcript — with the
    # `meta.json` Claude Code always writes with it, here a recorded one under the new name...
    subagents = corpus.session_dir / SPINE / "subagents"
    shutil.copy(
        FIXTURES / "dup_uuid" / f"{DUPS}.jsonl", subagents / "agent-a1d0bc50fe316ed8e.jsonl"
    )
    shutil.copy(
        subagents / "agent-af6473ae437c9608d.meta.json",
        subagents / "agent-a1d0bc50fe316ed8e.meta.json",
    )
    result = refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then the session is re-extracted under a new fingerprint...
    assert (transcript.stat().st_size, transcript.stat().st_mtime_ns) == unchanged
    assert result.extracted == [SPINE]
    assert extractor.extracted == [SPINE, SPINE]
    assert exporter.fingerprints() != before


def test_a_changed_offload_file_re_extracts_its_session(corpus: Corpus, exporter: DuckDbExporter):
    """Rewriting an offloaded tool result re-extracts the session and re-archives the file."""
    corpus.add("offload", OFFLOAD)
    extractor = CountingExtractor(corpus.extractor())
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)
    offloaded = corpus.session_dir / OFFLOAD / "tool-results" / "bosvr1kjx.txt"

    # If the file holding a tool's output changes while the transcript stands still...
    offloaded.write_text("[redacted] — a shorter output than before")
    result = refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then the session is parsed again, and the store holds the file as it now reads.
    assert result.extracted == [OFFLOAD]
    assert stored_rows(exporter.path, "SELECT content, size_bytes FROM offload_files") == [
        ("[redacted] — a shorter output than before", offloaded.stat().st_size)
    ]


def test_a_bumped_extractor_version_re_extracts_everything(
    corpus: Corpus, exporter: DuckDbExporter, monkeypatch: pytest.MonkeyPatch
):
    """Upgrading the parser re-parses the corpus rather than leaving old rows in place."""
    corpus.add("spine", SPINE)
    corpus.add("dup_uuid", DUPS)
    extractor = CountingExtractor(corpus.extractor())
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)
    before = exporter.fingerprints()

    # If the extractor's version changes with the files untouched...
    monkeypatch.setattr(claude_code, "EXTRACTOR_VERSION", "99")
    result = refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then every session is parsed again and every fingerprint moves.
    assert sorted(result.extracted) == sorted([DUPS, SPINE])
    assert len(extractor.extracted) == 4
    assert set(exporter.fingerprints()) == set(before)
    assert not set(exporter.fingerprints().values()) & set(before.values())


def test_a_pruned_session_keeps_its_rows(corpus: Corpus, exporter: DuckDbExporter):
    """Claude Code deletes transcripts after a few weeks; the store is the archive.

    Refresh only ever adds and replaces. A session whose file is gone stops being
    discovered, and its rows stay exactly as its last extract left them.
    """
    corpus.add("spine", SPINE)
    transcript = corpus.add("dup_uuid", DUPS)
    extractor = corpus.extractor()
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)
    before = table(exporter, "raw_records", DUPS)

    # If one session's transcript is pruned from disk...
    transcript.unlink()
    result = refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then discovery no longer sees it, and its rows survive untouched.
    assert [source.id for source in extractor.sessions(corpus.project)] == [SPINE]
    assert result.extracted == []
    assert table(exporter, "raw_records", DUPS) == before


def test_an_extract_leaves_the_store_readable_between_sessions(
    corpus: Corpus, exporter: DuckDbExporter
):
    """A viewer can read the store while an extract is running.

    The whole point of the exporter opening per operation: an extract spends most of its
    time parsing, and a reader that arrives during the parse should not have to wait out
    the run. The load-bearing probe is the second one — it lands after a session has
    already been written, which is exactly when a run that held its connection would still
    be holding it.
    """
    # If a two-session extract is asked, at each parse, whether another process can read...
    corpus.add("spine", SPINE)
    corpus.add("dup_uuid", DUPS)
    extractor = ProbingExtractor(corpus.extractor(), exporter.path)

    result = refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)

    # ...then the answer is yes both times, and both sessions still land.
    assert sorted(result.extracted) == sorted([DUPS, SPINE])
    assert extractor.readable == [True, True]


def test_the_cli_extract_command_writes_the_same_store(corpus: Corpus, tmp_path: Path):
    """`hp extract` drives the same pipeline the API does."""
    corpus.add("spine", SPINE)
    through_api = tmp_path / "api.duckdb"
    exporter = DuckDbExporter(through_api, wait=NO_WAIT)
    extractor = corpus.extractor()
    refresh(extractor.sessions(corpus.project), extractor=extractor, exporter=exporter)
    expected = table(exporter, "turns", SPINE)

    # If the CLI runs over the same corpus...
    through_cli = tmp_path / "cli.duckdb"
    cli.main(
        "extract",
        str(corpus.project),
        "--db",
        str(through_cli),
        "--projects-root",
        str(corpus.root),
    )

    # ...then it leaves the same rows behind.
    exporter = DuckDbExporter(through_cli, wait=NO_WAIT)
    assert table(exporter, "turns", SPINE) == expected


def test_an_extract_waits_out_a_holder_and_then_writes(corpus: Corpus, tmp_path: Path):
    """An extract that lands while something else holds the store queues behind it.

    The direction an operator meets first: `hp extract` typed while a page is being served.
    It used to fail on sight; now it waits out the request and writes.
    """
    corpus.add("spine", SPINE)
    db = tmp_path / "traces.duckdb"
    # The store has to exist before another process can hold it.
    DuckDbExporter(db, wait=NO_WAIT)

    # If someone else lets go of the store partway through the extract's first open...
    with locked(db, hold=BRIEF_HOLD):
        started = time.monotonic()
        cli.main(
            "extract",
            str(corpus.project),
            "--db",
            str(db),
            "--projects-root",
            str(corpus.root),
        )
        waited = time.monotonic() - started

    # ...then the extract queued for it, and wrote the session it was asked for.
    assert waited >= BRIEF_HOLD / 2
    assert stored_rows(db, "SELECT id FROM sessions") == [(SPINE,)]


def test_an_extract_gives_up_on_a_squatter_and_names_it(
    corpus: Corpus, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An extract that cannot have the store fails saying who has it, rather than hanging.

    The other direction of the wait: `hp extract` queues for `CLI_WAIT` and then stops. A
    budget that ran out has to leave an operator something to act on, so the process holding
    the file is named — DuckDB's own line, kept.
    """
    corpus.add("spine", SPINE)
    db = tmp_path / "traces.duckdb"
    # The store has to exist before another process can hold it.
    DuckDbExporter(db, wait=NO_WAIT)
    monkeypatch.setattr(cli, "CLI_WAIT", IMPATIENT)

    # If someone else is holding the store for longer than the extract will wait...
    with locked(db) as holder, pytest.raises(StoreLocked) as refused:
        cli.main(
            "extract",
            str(corpus.project),
            "--db",
            str(db),
            "--projects-root",
            str(corpus.root),
        )

    # ...then it says which store, and which process to go and look at.
    assert str(db) in str(refused.value)
    assert str(holder.pid) in str(refused.value)


def test_a_session_source_carries_every_file_it_owns(corpus: Corpus):
    """Discovery hands the extractor the whole session directory, not just the transcript."""
    corpus.add("spine", SPINE)
    offloaded = corpus.session_dir / SPINE / "tool-results" / "result.txt"
    offloaded.parent.mkdir(parents=True)
    offloaded.write_text("[redacted]")

    (source,) = corpus.extractor().sessions(corpus.project)

    # An offloaded tool result is part of the session, so it reaches the fingerprint and,
    # from slice 2 on, the parser.
    assert offloaded in source.files.files()


def test_a_typed_project_path_discovers_the_same_sources_as_its_directory(corpus: Corpus):
    """`sessions(project)` is `sessions_in()` over the directory the path encodes to."""
    corpus.add("spine", SPINE)
    extractor = corpus.extractor()

    # The two lists agree whole, fingerprints included.
    assert extractor.sessions(corpus.project) == extractor.sessions_in(corpus.session_dir)
    assert [source.id for source in extractor.sessions_in(corpus.session_dir)] == [SPINE]
