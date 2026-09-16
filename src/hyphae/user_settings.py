"""What `hp` remembers for a person between runs: `~/.hyphae/settings.json`.

A preference is the person's, not the archive's, so it sits beside the store rather than in
it, and `--db` does not move it. The file is one JSON object namespaced by command:
`{"extract": {"projects": [...]}}`. Each command owns the shape under its own key.
"""

import json
from pathlib import Path
from typing import Any

from hyphae.store_path import STORE_DIR

SETTINGS_NAME = "settings.json"


def default_path() -> Path:
    """`~/.hyphae/settings.json`, read from the home directory at call time — never from
    `HP_DB`, which names the store and nothing else."""
    return Path.home() / STORE_DIR / SETTINGS_NAME


def read(path: Path | None = None) -> dict[str, Any]:
    """The whole settings mapping; an empty one when the file does not exist yet.

    A file that is not JSON raises: a preference a person wrote is something to look at,
    not something to silently forget.
    """
    path = default_path() if path is None else path
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def write(settings: dict[str, Any], path: Path | None = None) -> None:
    """Replace the settings file with `settings`, making the directory above it."""
    path = default_path() if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
