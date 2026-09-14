"""What the environment tells the package, read once at import.

One constant so far: whether this process is a test run. The record models claim to describe
every record kind Claude Code writes and every field on the ones a reader opens, and the tallies
in `extract/records/unknown.py` hold them to it — strictly where a person is looking, and as a
tally in an extract, which is what `UNIT_TESTING` decides (`plans/records-as-parser/design.md`).
"""

import os

# `pytest-env` sets it for every pytest invocation, `pyproject.toml` says so, and nothing else
# does: a bare `uv run pytest` on one file has to be strict too, or a leaf would prove nothing.
UNIT_TESTING: bool = os.environ.get("UNIT_TESTING") == "1"
