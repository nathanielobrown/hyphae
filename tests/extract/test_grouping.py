"""Which repository a recorded working directory extends: `base_project()`.

The path rule is proved on strings nothing on disk backs, the git refinement on a real
repository and worktree built once under `tmp_path`. Nothing here reads a directory outside
`tmp_path`: the one recorded path is re-rooted under a directory that exists nowhere.
"""

import os
import subprocess
from pathlib import Path

import pytest

from hyphae.extract.grouping import base_project
from tests.conftest import MYCELIA

# One worker builds the repository, and the leaves that read it run beside it.
pytestmark = pytest.mark.xdist_group("git_repo")

# The `cwd` `spine/` recorded in the worktree Claude Code cut for a triage run. The path may or
# may not exist where the suite runs (it does on the recording machine), so the leaf below moves
# it under a root that exists nowhere, and the path rule is all that can place it.
RECORDED_WORKTREE = Path(f"{MYCELIA}/.claude/worktrees/wk-triage")
GONE = Path("/gone")

# Sever the host's git config: a global `init.templateDir` or a hook would make the repository
# below depend on the machine that built it.
HERMETIC_GIT = {
    **{k: v for k, v in os.environ.items() if k != "GIT_TEMPLATE_DIR"},
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@invalid",
}


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=HERMETIC_GIT, check=True, timeout=30)


@pytest.fixture(scope="module")
def repos(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`repos/a`, a repository with a subdirectory and one commit; `repos/wt`, a worktree cut
    beside it — the layout this checkout uses. Built once for the module."""
    repos = tmp_path_factory.mktemp("repos")
    repo = repos / "a"
    (repo / "src" / "pkg").mkdir(parents=True)
    git("init", "-q", "--template=", cwd=repo)
    git("commit", "-q", "--allow-empty", "-m", "init", cwd=repo)
    git("worktree", "add", "-q", "../wt", cwd=repo)
    return repos


def test_a_deleted_claude_worktree_folds_to_the_repository_above_it() -> None:
    """A worktree Claude Code cut under `.claude/worktrees/` and since deleted still groups under
    the repository, by the path alone."""
    deleted = GONE / RECORDED_WORKTREE.relative_to("/")
    assert not (GONE / Path(MYCELIA).relative_to("/")).exists()
    assert base_project(deleted) == GONE / Path(MYCELIA).relative_to("/")


def test_a_worktrees_segment_folds_and_so_does_a_subdirectory_below_it() -> None:
    """A `worktrees/<name>` segment without `.claude` cuts the same way, wherever it sits."""
    # Invented paths: nothing under `/x` exists, so no git call can answer.
    assert base_project(Path("/x/worktrees/w/src")) == Path("/x")
    assert base_project(Path("/x/worktrees/w")) == Path("/x")


def test_a_repository_root_maps_to_itself_as_an_absolute_path(repos: Path) -> None:
    """A repository is its own base project, and the answer is a full path."""
    # From the top level `git rev-parse --git-common-dir` prints the relative `.git`, so a
    # naive parent of it would be `.`.
    assert base_project(repos / "a") == (repos / "a").resolve()


def test_a_subdirectory_of_a_repository_maps_to_the_repository(repos: Path) -> None:
    """A session that ran in a package directory groups under the repository holding it."""
    assert base_project(repos / "a" / "src" / "pkg") == (repos / "a").resolve()


def test_a_live_worktree_beside_its_repository_maps_to_the_repository(repos: Path) -> None:
    """A worktree cut next to the repository, which no path rule reaches, still groups under
    the repository it was cut from."""
    assert base_project(repos / "wt") == (repos / "a").resolve()


def test_a_directory_inside_no_repository_maps_to_itself(tmp_path: Path) -> None:
    """A working directory git knows nothing about is its own base project, and git's refusal
    is not an error."""
    assert base_project(tmp_path) == tmp_path


def test_a_parent_of_repositories_does_not_fold_into_any_of_them(repos: Path) -> None:
    """The directory repositories are checked out under stays its own project rather than
    swallowing every repository beneath it."""
    assert base_project(repos) == repos


def test_a_path_that_does_not_exist_and_matches_no_rule_maps_to_itself() -> None:
    """A deleted working directory with no worktree segment groups under nothing but itself."""
    # Invented path.
    assert base_project(Path("/gone/x")) == Path("/gone/x")
