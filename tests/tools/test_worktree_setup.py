"""A worktree comes up ready to work, however it was made.

Each leaf builds a throwaway repository holding this repo's hook scripts, installs the hooks the
way `mise run setup` does, and drives real `git worktree add` and `git commit` against it. A
stub `mise` first on PATH writes down what provisioning asked of it, so nothing syncs a real
virtualenv and nothing reaches the network. The `SessionStart` path runs the same
`tools/setup-worktree`, so what holds here holds there.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# Every leaf copies this repo's hook scripts into its throwaway repository.
pytestmark = pytest.mark.reads_the_repo

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ("install-hooks", "setup-worktree", "post-checkout")

# What provisioning copies, planted in the primary checkout: a file, a nested file, and a line
# naming nothing the primary holds, which is skipped rather than an error.
INCLUDE = """\
# Copied into every new worktree.
.env
.claude/settings.local.json   # trailing comment
missing.txt
"""
SECRETS = {".env": "SYNTHETIC_KEY=probe\n", ".claude/settings.local.json": "{}\n"}

# Ceiling on one git command or script run; each takes well under a second.
TIMEOUT = 30


def git(cwd: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    """An environment whose `mise` is a stub that logs its arguments and cwd to `mise.log`.

    `STUB_MISE_EXIT` sets what it answers, so a leaf can make every mise call fail.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "mise"
    stub.write_text(
        f'#!/usr/bin/env bash\necho "$(pwd -P): $*" >> {tmp_path}/mise.log\n'
        'echo "stub mise stdout"\nexit "${STUB_MISE_EXIT:-0}"\n'
    )
    stub.chmod(0o755)
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }


def mise_calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "mise.log"
    return log.read_text().splitlines() if log.exists() else []


@pytest.fixture
def primary(tmp_path: Path, env: dict[str, str]) -> Path:
    """A primary checkout on `main`: one commit without the hook scripts, one with them, and
    the hooks installed. The gitignored files `INCLUDE` lists sit in its tree."""
    repo = tmp_path / "primary"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main", env=env)
    (repo / "README").write_text("before provisioning\n")
    git(repo, "add", ".", env=env)
    git(repo, "commit", "-q", "-m", "predates the scripts", env=env)
    git(repo, "tag", "old", env=env)

    (repo / "tools").mkdir()
    for name in SCRIPTS:
        shutil.copy2(ROOT / "tools" / name, repo / "tools" / name)
    (repo / ".worktreeinclude").write_text(INCLUDE)
    (repo / ".gitignore").write_text("".join(f"{path}\n" for path in SECRETS))
    git(repo, "add", ".", env=env)
    git(repo, "commit", "-q", "-m", "adds the scripts", env=env)
    for path, text in SECRETS.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)

    subprocess.run(
        [repo / "tools" / "install-hooks"],
        cwd=repo,
        env=env,
        capture_output=True,
        timeout=TIMEOUT,
        check=True,
    )
    return repo


def test_a_new_worktree_gets_the_included_files_and_a_synced_venv(
    tmp_path: Path, primary: Path, env: dict[str, str]
) -> None:
    # Made the way a person or Orca makes one: `git worktree add`, hooks on.
    tree = tmp_path / "anywhere" / "topic"
    added = git(primary, "worktree", "add", "-q", str(tree), "-b", "topic", env=env)
    assert added.returncode == 0, added.stderr

    # Every listed file the primary holds was copied, nested ones included; the line naming
    # nothing was skipped.
    for path, text in SECRETS.items():
        assert (tree / path).read_text() == text
    assert not (tree / "missing.txt").exists()

    # mise was asked to trust the new checkout, then to run the `sync` task that owns the flags.
    real = tree.resolve()
    assert mise_calls(tmp_path) == [f"{real}: trust -q", f"{real}: run sync"]
    # The stub printed to stdout; none of it may reach a `SessionStart` hook's context.
    assert "stub mise stdout" not in added.stdout


def test_provisioning_never_fails_the_checkout_and_never_writes_stdout(
    tmp_path: Path, primary: Path, env: dict[str, str]
) -> None:
    # Every mise call fails, as it would on a machine that cannot sync.
    tree = tmp_path / "topic"
    failing = {**env, "STUB_MISE_EXIT": "1"}
    added = git(primary, "worktree", "add", "-q", str(tree), "-b", "topic", env=failing)
    assert added.returncode == 0, added.stderr
    assert "sync failed" in added.stderr

    # Run directly, as `SessionStart` runs it: still zero, and silent on stdout.
    direct = subprocess.run(
        [tree / "tools" / "setup-worktree"],
        cwd=tree,
        env=failing,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    assert (direct.returncode, direct.stdout) == (0, "")


def test_a_file_already_in_the_worktree_is_left_alone(
    tmp_path: Path, primary: Path, env: dict[str, str]
) -> None:
    tree = tmp_path / "topic"
    git(primary, "worktree", "add", "-q", str(tree), "-b", "topic", env=env)
    (tree / ".env").write_text("THIS_CHECKOUT=own\n")

    subprocess.run(
        [tree / "tools" / "setup-worktree"], cwd=tree, env=env, timeout=TIMEOUT, check=True
    )
    assert (tree / ".env").read_text() == "THIS_CHECKOUT=own\n"


def test_a_branch_switch_does_not_provision_again(
    tmp_path: Path, primary: Path, env: dict[str, str]
) -> None:
    tree = tmp_path / "topic"
    git(primary, "worktree", "add", "-q", str(tree), "-b", "topic", env=env)
    provisioned = mise_calls(tmp_path)
    assert provisioned, "the add itself never provisioned, so this leaf would prove nothing"

    switched = git(tree, "switch", "-q", "-c", "other", env=env)
    assert switched.returncode == 0, switched.stderr
    assert mise_calls(tmp_path) == provisioned


def test_a_checkout_older_than_the_scripts_adds_cleanly_but_cannot_commit(
    tmp_path: Path, primary: Path, env: dict[str, str]
) -> None:
    # The old commit has no `tools/post-checkout`: the add must still succeed, quietly.
    tree = tmp_path / "old"
    added = git(primary, "worktree", "add", "-q", str(tree), "-b", "old-topic", "old", env=env)
    assert (added.returncode, added.stderr) == (0, "")
    assert mise_calls(tmp_path) == []

    # It has no `tools/pre-commit` either, and the gate refuses rather than waving it through.
    (tree / "README").write_text("changed\n")
    git(tree, "add", "README", env=env)
    committed = git(tree, "commit", "-q", "-m", "change", env=env)
    assert committed.returncode == 1
    assert "no pre-commit script found" in committed.stderr


def test_the_hook_dispatcher_drops_an_inherited_virtualenv(
    tmp_path: Path, primary: Path, env: dict[str, str]
) -> None:
    # A stand-in gate that fails with whatever VIRTUAL_ENV it was handed.
    gate = primary / "tools" / "pre-commit"
    gate.write_text('#!/usr/bin/env bash\necho "VIRTUAL_ENV=${VIRTUAL_ENV-unset}" >&2\nexit 1\n')
    gate.chmod(0o755)

    # The committer's shell still has another checkout's venv active.
    inherited = {**env, "VIRTUAL_ENV": str(tmp_path / "elsewhere" / ".venv")}
    committed = git(primary, "commit", "-q", "--allow-empty", "-m", "x", env=inherited)
    assert "VIRTUAL_ENV=unset" in committed.stderr


def test_every_path_worktreeinclude_names_is_gitignored() -> None:
    """A tracked path needs no copy, and a path listed by mistake would be copied forever."""
    lines = (ROOT / ".worktreeinclude").read_text().splitlines()
    paths = [path for line in lines if (path := line.split("#")[0].strip())]
    assert paths, "`.worktreeinclude` lists nothing, so this leaf is checking nothing"
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=True,
    )
    assert sorted(ignored.stdout.split()) == sorted(paths)
