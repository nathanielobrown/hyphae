import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from hyphae.extract.layout import SessionFiles, find_project_dirs, find_sessions
from hyphae.projects import encode_project_path
from tests.conftest import FIXTURES


def make_projects_root(tmp_path: Path, project: Path, session_ids: list[str]) -> Path:
    """Build the on-disk shape Claude Code writes, as observed under ~/.claude/projects.

    A session is `<root>/<encoded-cwd>/<session-id>.jsonl`, with its subagent runs in a
    sibling directory named for the session. Content doesn't matter here — discovery is
    about the layout, and the parser tests own the records. `copy_fixture` fills a directory
    with a real transcript where content does.
    """
    root = tmp_path / "projects"
    project_dir = root / encode_project_path(project)
    project_dir.mkdir(parents=True)
    for session_id in session_ids:
        (project_dir / f"{session_id}.jsonl").write_text("")
    return root


def copy_fixture(project_dir: Path, fixture: str, *, written_at: datetime | None = None) -> Path:
    """Copy one fixture transcript, and the session directory beside it if it has one, into a
    project directory. `written_at` sets the transcript's mtime, which discovery reads as when
    the session was last written; None leaves the copy's own clock. Returns the transcript."""
    source = next(FIXTURES.rglob(f"{fixture}.jsonl"))
    project_dir.mkdir(parents=True, exist_ok=True)
    transcript = project_dir / source.name
    shutil.copy(source, transcript)
    if source.with_suffix("").is_dir():
        shutil.copytree(source.with_suffix(""), transcript.with_suffix(""), dirs_exist_ok=True)
    if written_at is not None:
        os.utime(transcript, (written_at.timestamp(), written_at.timestamp()))
    return transcript


def test_find_sessions_returns_every_transcript_for_a_project(tmp_path: Path):
    """Every session transcript in a project's directory is discovered, sorted by id."""
    # If a project has three recorded sessions...
    project = Path("/Users/nob/repos/mycelia")
    root = make_projects_root(tmp_path, project, ["c-third", "a-first", "b-second"])
    # ...then all three come back, in a stable order...
    sessions = find_sessions(root / encode_project_path(project))
    assert [s.id for s in sessions] == ["a-first", "b-second", "c-third"]
    # ...each carrying the path to its own transcript.
    assert sessions[0] == SessionFiles(
        id="a-first",
        transcript=root / "-Users-nob-repos-mycelia" / "a-first.jsonl",
    )


def test_find_sessions_ignores_non_transcript_files(tmp_path: Path):
    """Only `.jsonl` files count as sessions — the tree also holds metadata and scratch."""
    project = Path("/Users/nob/repos/mycelia")
    root = make_projects_root(tmp_path, project, ["real-session"])
    project_dir = root / encode_project_path(project)
    (project_dir / "notes.md").write_text("")
    (project_dir / "agent-abc.meta.json").write_text("")

    assert [s.id for s in find_sessions(project_dir)] == ["real-session"]


def test_find_sessions_ignores_the_subagent_tree(tmp_path: Path):
    """A subagent run belongs to its session, so it is never returned as a session of its own."""
    # If a session spawned two subagents, whose transcripts sit under the session's own directory...
    project = Path("/Users/nob/repos/mycelia")
    root = make_projects_root(tmp_path, project, ["parent-session"])
    subagents = root / encode_project_path(project) / "parent-session" / "subagents"
    subagents.mkdir(parents=True)
    (subagents / "agent-aaa.jsonl").write_text("")
    (subagents / "agent-bbb.jsonl").write_text("")
    # ...then only the parent is a session...
    sessions = find_sessions(root / encode_project_path(project))
    assert [s.id for s in sessions] == ["parent-session"]
    # ...and its subagent transcripts hang off it.
    assert sessions[0].subagent_transcripts() == [
        subagents / "agent-aaa.jsonl",
        subagents / "agent-bbb.jsonl",
    ]


def test_find_sessions_finds_subagents_nested_under_a_workflow(tmp_path: Path):
    """A parallel fan-out nests its agents a level deeper; they are still the session's."""
    project = Path("/Users/nob/repos/mycelia")
    root = make_projects_root(tmp_path, project, ["parent-session"])
    workflow = root / encode_project_path(project) / "parent-session" / "subagents" / "workflows"
    (workflow / "wf_1").mkdir(parents=True)
    (workflow / "wf_1" / "agent-ccc.jsonl").write_text("")

    session = find_sessions(root / encode_project_path(project))[0]
    assert session.subagent_transcripts() == [workflow / "wf_1" / "agent-ccc.jsonl"]


def test_a_session_with_no_subagents_has_none(tmp_path: Path):
    """A session that spawned no subagents reports an empty list, not an error."""
    project = Path("/Users/nob/repos/mycelia")
    root = make_projects_root(tmp_path, project, ["solo-session"])

    assert find_sessions(root / encode_project_path(project))[0].subagent_transcripts() == []


def test_find_sessions_raises_when_the_project_has_no_recorded_sessions(tmp_path: Path):
    """An unknown project is a mistake to surface, not an empty result to quietly return."""
    # If the project has never been opened in Claude Code, no directory exists for it...
    root = tmp_path / "projects"
    root.mkdir()
    # ...so the caller hears about it, and the error names the directory that was looked in.
    with pytest.raises(FileNotFoundError) as excinfo:
        find_sessions(root / encode_project_path(Path("/Users/nob/repos/nonexistent")))
    assert str(root / "-Users-nob-repos-nonexistent") in str(excinfo.value)


def test_find_project_dirs_returns_only_directories_holding_a_transcript(tmp_path: Path):
    """A project directory is one with a session transcript directly under it, by name.

    Invented layout: the tree also holds an empty directory, one holding only a session's
    subdirectory, and a stray file, none of which is a project.
    """
    # If the root holds two project directories with transcripts, listed out of order...
    root = make_projects_root(tmp_path, Path("/Users/nob/repos/mycelia"), ["s1"])
    make_projects_root(tmp_path, Path("/Users/nob/repos/hyphae"), ["s2"])
    # ...beside an empty directory, a directory holding only a session subdirectory, and a file...
    (root / "-Users-nob-repos-empty").mkdir()
    (root / "-Users-nob-repos-pruned" / "s3" / "subagents").mkdir(parents=True)
    (root / "stray.txt").write_text("")
    # ...then only the two with a top-level transcript are projects, sorted by name.
    assert find_project_dirs(root) == [
        root / "-Users-nob-repos-hyphae",
        root / "-Users-nob-repos-mycelia",
    ]


def test_find_project_dirs_raises_when_the_root_does_not_exist(tmp_path: Path):
    """A missing projects root means Claude Code never ran here, which is not an empty corpus."""
    with pytest.raises(FileNotFoundError) as excinfo:
        find_project_dirs(tmp_path / "projects")
    assert str(tmp_path / "projects") in str(excinfo.value)
