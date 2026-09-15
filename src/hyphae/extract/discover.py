"""Every project directory under a projects root, described for a person choosing among them.

One walk of the root: for each directory holding a transcript, where its newest session ran,
how many sessions it holds, how many were written this week, and which repository it extends
(`extract/grouping.py`). The picker sorts and folds these rows; it is the only caller, since
the walk reads a transcript per directory and the other extract scopes read nothing before
they refresh.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from hyphae import settings
from hyphae.extract.errors import TranscriptSchemaError
from hyphae.extract.grouping import base_project
from hyphae.extract.layout import find_project_dirs, find_sessions
from hyphae.extract.records.base import SessionContext
from hyphae.extract.records.unknown import Unknowns
from hyphae.extract.transcript import iter_lines

logger = logging.getLogger(__name__)

# How far back a session counts as recent: a week is long enough to hold a project a person
# touches on working days, and short enough to drop a checkout an eval created and deleted.
RECENT_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class ProjectDir:
    """One directory under the projects root, as a picker row."""

    # The directory name under the root: what `settings.json` stores, since Claude Code's
    # encoding is lossy and the recorded `cwd` does not round-trip to a directory.
    name: str
    directory: Path
    # From the newest transcript that records one; None labels the row by name.
    cwd: Path | None
    # `base_project(cwd)`; None when `cwd` is None.
    base: Path | None
    # Top-level transcripts: subagent transcripts belong to a session, not beside one.
    sessions: int
    # Of those, written within `RECENT_WINDOW` of the clock `discover()` was handed.
    recent: int

    @property
    def label(self) -> str:
        """What a page or a picker prints for the row: where it ran, else the directory name."""
        return str(self.cwd) if self.cwd is not None else self.name


def discover(projects_root: Path, *, now: datetime) -> list[ProjectDir]:
    """Every project directory under the root, sorted by recent desc, sessions desc, name.

    `now` is the timezone-aware clock `recent` counts back from. Raises `FileNotFoundError`
    when the root is missing, as `find_project_dirs` does.
    """
    cutoff = (now - RECENT_WINDOW).timestamp()
    rows = []
    for directory in find_project_dirs(projects_root):
        written = {
            session.transcript: session.transcript.stat().st_mtime
            for session in find_sessions(directory)
        }
        newest = max(written, key=written.__getitem__)
        try:
            cwd = recorded_cwd(newest)
        except TranscriptSchemaError as error:
            # A shape the parser does not know, and only that: the walk crosses hundreds of
            # scratch directories, and one drifted transcript must not hide the rest. The row
            # keeps its name, and an extract over it refuses the session properly.
            logger.warning(
                "%s: labelled by name, its newest transcript is refused: %s", directory.name, error
            )
            cwd = None
        rows.append(
            ProjectDir(
                name=directory.name,
                directory=directory,
                cwd=cwd,
                base=base_project(cwd) if cwd is not None else None,
                sessions=len(written),
                recent=sum(1 for mtime in written.values() if mtime >= cutoff),
            )
        )
    return sorted(rows, key=lambda row: (-row.recent, -row.sessions, row.name))


def recorded_cwd(transcript: Path) -> Path | None:
    """Where a transcript's session ran: the first record that carries a `cwd`, or None.

    Reads through the record models and stops at the first sited record, so a long transcript
    costs a few lines. A transcript whose records all lack one — a fork that inherited its
    context by reference — has no answer.
    """
    # The tally is this read's own: the extract that follows re-reads every record it counts.
    unknowns = Unknowns(strict=settings.UNIT_TESTING)
    for line in iter_lines(transcript, transcript.stem, unknowns):
        if isinstance(line.record, SessionContext) and line.record.cwd is not None:
            return Path(line.record.cwd)
    return None
