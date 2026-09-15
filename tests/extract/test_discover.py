"""What `discover()` says about each project directory under a root: where its sessions ran,
how many there are, how many are recent, and which repository it extends."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hyphae.extract.discover import ProjectDir, discover
from hyphae.projects import encode_project_path
from tests.conftest import FIXTURES, MYCELIA, SPINE
from tests.extract.test_layout import copy_fixture

# A pinned clock, so "within seven days" is a fact about the fixture's mtime and not the run's.
NOW = datetime(2026, 9, 15, 12, tzinfo=UTC)
MYCELIA_DIR = encode_project_path(Path(MYCELIA))
# `invented-truncated-tail` ran under `/repo`: invented content, but the one clean transcript
# with a `cwd` unlike every recorded fixture's.
OTHER = "invented-truncated-tail"
OTHER_CWD = Path("/repo")


def days_ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


def test_cwd_comes_from_the_first_record_carrying_one_in_the_newest_transcript(
    tmp_path: Path,
) -> None:
    """A directory is labelled by where its most recently written session ran, read past the
    bookkeeping records that open a transcript with no `cwd`."""
    # If a directory holds `spine/` — whose first five records carry no `cwd` — beside a
    # transcript recorded under `/repo`, and the invented one was written last...
    root = tmp_path / "projects"
    copy_fixture(root / MYCELIA_DIR, SPINE, written_at=days_ago(2))
    copy_fixture(root / MYCELIA_DIR, OTHER, written_at=days_ago(1))
    # ...then the directory reads as `/repo`, and that is its label...
    [row] = discover(root, now=NOW)
    assert (row.cwd, row.label) == (OTHER_CWD, str(OTHER_CWD))
    # ...and with `spine` written last, as the mycelia checkout.
    copy_fixture(root / MYCELIA_DIR, SPINE, written_at=days_ago(0))
    assert [row.cwd for row in discover(root, now=NOW)] == [Path(MYCELIA)]


def test_a_directory_whose_newest_transcript_has_no_cwd_is_labelled_by_name(
    tmp_path: Path,
) -> None:
    """A fork that inherited its context carries no `cwd`; its directory keeps its name."""
    # If the only transcript is `fork_byref/`'s main one, three records and no `cwd`...
    root = tmp_path / "projects"
    fork = "07a769d7-828c-4edb-b3ce-af51e2712aa3"
    copy_fixture(root / MYCELIA_DIR, fork, written_at=days_ago(1))
    # ...then the row has no working directory and no base, and is labelled by name.
    [row] = discover(root, now=NOW)
    assert row == ProjectDir(
        name=MYCELIA_DIR,
        directory=root / MYCELIA_DIR,
        cwd=None,
        base=None,
        sessions=1,
        recent=1,
    )
    assert row.label == MYCELIA_DIR


def test_sessions_counts_top_level_transcripts_only(tmp_path: Path) -> None:
    """A session's subagent transcripts are part of it, not sessions of their own."""
    # If `spine/` is copied with its `subagents/` directory of two agent transcripts...
    root = tmp_path / "projects"
    transcript = copy_fixture(root / MYCELIA_DIR, SPINE, written_at=days_ago(1))
    assert len(list((transcript.with_suffix("") / "subagents").glob("*.jsonl"))) == 2
    # ...then the directory holds one session.
    [row] = discover(root, now=NOW)
    assert (row.sessions, row.recent) == (1, 1)


def test_recent_counts_transcripts_written_within_seven_days(tmp_path: Path) -> None:
    """A session written more than a week ago counts as a session, but not as recent."""
    # If three copies of one transcript were written 1, 6 and 8 days ago (invented mtimes)...
    root = tmp_path / "projects"
    for days in (1, 6, 8):
        copy_fixture(root / MYCELIA_DIR, OTHER, written_at=days_ago(days)).rename(
            root / MYCELIA_DIR / f"copy-{days}.jsonl"
        )
    # ...then all three are sessions and two are recent.
    [row] = discover(root, now=NOW)
    assert (row.sessions, row.recent) == (3, 2)


def test_base_is_the_repository_the_cwd_extends(tmp_path: Path) -> None:
    """A directory recorded in a worktree groups under the repository the worktree was cut from."""
    # If the newest transcript's first sited record is the one `spine/` borrowed from a run in
    # `.claude/worktrees/wk-triage` — an invented transcript of that one real record...
    root = tmp_path / "projects"
    worktree = f"{MYCELIA}/.claude/worktrees/wk-triage"
    spine = next(FIXTURES.rglob(f"{SPINE}.jsonl")).read_text().split("\n")
    borrowed = next(raw for raw in spine if json.loads(raw).get("cwd") == worktree)
    directory = root / encode_project_path(Path(worktree))
    directory.mkdir(parents=True)
    (directory / "invented-worktree-session.jsonl").write_text(borrowed + "\n")
    # ...then the row's base is the repository above the worktree.
    [row] = discover(root, now=NOW)
    assert (row.cwd, row.base) == (Path(worktree), Path(MYCELIA))


def test_rows_sort_by_recent_then_sessions_then_name(tmp_path: Path) -> None:
    """The busiest directories come first: most recent sessions, then most sessions, then name."""
    # If four directories are laid out so that each key alone would misorder them: `d` has the
    # most sessions but none recent, `c` and `b` tie on both counts, and `a` has one of each...
    root = tmp_path / "projects"
    layout = {"-d": [10, 10, 10], "-c": [1, 10], "-b": [1, 10], "-a": [1]}
    for name, ages in layout.items():
        for index, days in enumerate(ages):
            copy_fixture(root / name, OTHER, written_at=days_ago(days)).rename(
                root / name / f"copy-{index}.jsonl"
            )
    # ...then `c` and `b` lead on recency, `b` before `c` by name, then `a`, then `d`.
    assert [row.name for row in discover(root, now=NOW)] == ["-b", "-c", "-a", "-d"]
