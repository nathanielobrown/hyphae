"""Which repository a recorded working directory extends, so a picker can fold its worktrees.

Only 28 of the 250 working directories Claude Code recorded on the design machine still exist,
so the rule works from the path string first and asks git only where the path is on disk. What
a project *is* to the store's queries is `hyphae/projects.py`; this is the one place to replace
when grouping moves to something like a git remote.
"""

import subprocess
from pathlib import Path

# Where a worktree sits: Claude Code cuts its own under `<repo>/.claude/worktrees/<name>`, and a
# person's convention is `<repo>/worktrees/<name>`. Either segment says the repository is above.
WORKTREES_DIR = "worktrees"
CLAUDE_DIR = ".claude"

# `git rev-parse` answers in milliseconds; the ceiling is for a hung filesystem, not git.
GIT_TIMEOUT = 10


def base_project(cwd: Path) -> Path:
    """The repository a working directory extends, or the directory itself.

    Path rule first: cut at a `.claude/worktrees/<name>` or `worktrees/<name>` segment. Then,
    if what remains exists on disk and is inside a git repository, the parent of
    `git rev-parse --git-common-dir` — one call, which folds a subdirectory into its
    repository and a live worktree into the repository it was cut from. Git's refusal
    (a directory in no repository) leaves the path as it stands.
    """
    base = _cut_at_worktree(cwd)
    if not base.is_dir():
        return base
    asked = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],  # noqa: S607 — whichever git is on PATH
        cwd=base,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
        check=False,
    )
    if asked.returncode != 0:
        return base
    # At a repository's top level git prints the relative `.git`, and from a subdirectory a
    # relative `../../.git`, so the answer is resolved against the directory it was asked in.
    return (base / asked.stdout.strip()).resolve().parent


def _cut_at_worktree(cwd: Path) -> Path:
    """The path above the first `worktrees/<name>` segment, or the path unchanged."""
    parts = cwd.parts
    for index, part in enumerate(parts[:-1]):
        if part == WORKTREES_DIR:
            above = Path(*parts[:index])
            return above.parent if above.name == CLAUDE_DIR else above
    return cwd
