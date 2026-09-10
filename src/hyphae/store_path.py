"""Where `hp` keeps its archive when no `--db` names one."""

import os
from pathlib import Path

# Names the store outright — the whole path to the file, not a directory to hang a name under.
# One variable is what lets a shell, a scheduled job, or a test point every `hp` command at the
# same archive without repeating `--db`.
HP_DB = "HP_DB"

# The dotdir in the home directory, and the file inside it: a dotdir is where a person looks
# for what one tool keeps on their machine, and the file name says what the directory holds.
STORE_DIR = ".hyphae"
STORE_NAME = "traces.duckdb"


def default_store() -> Path:
    """The one archive `hp` reads and writes unless `--db` says otherwise: `$HP_DB`, else
    `~/.hyphae/traces.duckdb`.

    Resolves a path and touches no disk. One archive serves every checkout, whatever
    directory a command runs from, and an extract can never land in a commit. The directories
    above it are made by the first write (`export/duckdb.py`).
    """
    named = os.environ.get(HP_DB)
    # An exported-but-empty variable is what an unset shell variable expands to. Falling back
    # would archive a caller's sessions somewhere they did not ask for and cannot find.
    if named is not None and not named.strip():
        raise SystemExit(f"{HP_DB} is set to nothing: name a store file with it, or unset it")
    if named:
        return Path(named)
    return Path.home() / STORE_DIR / STORE_NAME
