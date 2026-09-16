"""What `uv tool install` ships: the whole package, one `hp`, a command that runs anywhere, and
a `--dev` that refuses rather than hangs.

The dev environment is editable, so a path that reaches out of the package into the checkout,
or a `[tool.hatch]` exclude that drops a `.sql` or a `.css`, passes every other tier and breaks
the first installed user. Only a real non-editable install can show that, so this leaf performs
one — from the lock, offline, the same wheel through the same build a tool install runs.
"""

import configparser
import os
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "hyphae"


def _installed_files(root: Path) -> set[Path]:
    """Every file below `root`, relative to it, bytecode caches left out."""
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def _source_files() -> set[Path]:
    """Every file under `src/hyphae` hatchling ships: tracked or untracked, never gitignored —
    so a stray `.DS_Store` or `.pyc` on this machine is not a packaging regression."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", PACKAGE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {
        Path(name).relative_to(PACKAGE.relative_to(ROOT)) for name in listed.split("\0") if name
    }


# A real `uv` install and three `hp` subprocesses: seconds of wall clock, and the one level at
# which "reaches outside the package" and "installed without the dev group" are observable.
# Reads `src/` and `uv.lock`, so the mutation run drops it — the `mutants/` copy has no lock to
# install from.
@pytest.mark.slow
@pytest.mark.reads_the_repo
def test_the_installed_package_is_whole_and_runs_from_anywhere(tmp_path: Path) -> None:
    """A non-editable install carries every file under `src/hyphae`, exposes `hp` as its one
    command, answers `hp query --list` from a directory with no checkout above it, and refuses
    `hp view --dev` on one line rather than hanging."""
    # If the package is installed the way a tool install builds it — from the lock, offline
    # (`mise run sync` cached every wheel), without the dev group, and rebuilt rather than
    # taken from uv's build cache, which would miss a file added since the last build...
    venv = tmp_path / "venv"
    subprocess.run(
        [
            "uv",
            "sync",
            "--no-editable",
            "--no-dev",
            "--locked",
            "--offline",
            "--reinstall-package",
            "hyphae",
        ],
        cwd=ROOT,
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(venv)},
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    # ...then the installed package holds exactly the files git sees in the source tree —
    # hatchling honours `.gitignore` — a whole-set comparison, so a dropped `.sql` or `.css`
    # prints its name...
    site_packages = next(venv.glob("lib/python*/site-packages"))
    assert _installed_files(site_packages / "hyphae") == _source_files()
    # ...and `hp` is the one console script, bound to the CLI's entry point...
    entry_points = configparser.ConfigParser()
    entry_points.read(next(site_packages.glob("hyphae-*.dist-info")) / "entry_points.txt")
    assert dict(entry_points["console_scripts"]) == {"hp": "hyphae.cli:main"}
    # ...and from a directory with no checkout above it, with a home of its own, the installed
    # command prints its help and lists the query library...
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    environment = {**os.environ, "HOME": str(tmp_path / "home")}
    hp = venv / "bin" / "hp"
    for arguments in (["--help"], ["query", "--list"]):
        done = subprocess.run(
            [hp, *arguments],
            cwd=elsewhere,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert done.returncode == 0, done.stderr
    assert "session_counts" in done.stdout
    # ...and creates no store where it was run from...
    assert list(elsewhere.iterdir()) == []
    # ...and `--dev`, which needs the dev group this install does not carry, exits on one line
    # naming the checkout remedy — before opening the store it was given — rather than dying
    # in uvicorn's reload worker and leaving the supervisor waiting for a save that never
    # comes. The deadline is what turns that hang into a red.
    store = tmp_path / "never-opened.duckdb"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    refused = subprocess.run(
        [hp, "view", "--dev", "--no-browser", "--db", store, "--port", str(port)],
        cwd=elsewhere,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert refused.returncode != 0
    assert "uv run hp view --dev" in refused.stderr, refused.stderr
    assert not store.exists()
