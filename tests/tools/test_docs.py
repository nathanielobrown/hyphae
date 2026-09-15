"""What the prose tells a reader to type: an installed `hp`, not the checkout's `uv run hp`.

`hp` installs as a tool, so a user has no checkout to run `uv run` in. A doc that says
`uv run hp` is speaking to a contributor, and only one command needs to: `hp view --dev`, which
wants the dev group only the checkout's environment carries (`docs/ui-development.md`).
"""

import pytest

from tests.tools.conftest import ROOT

# The prose a user reads. `README.md` is the quickstart a doc-writer owns; it joins this sweep,
# with the one hit its "Work on hyphae" sentence keeps, once it is rewritten around `hp`.
DOCS = [*sorted(ROOT.glob("docs/*.md")), ROOT / "CLAUDE.md", ROOT / "CONTEXT.md"]

# Where `uv run hp` may still appear, and how often: an equality, so a line that creeps in
# elsewhere is a red rather than an allowlist quietly growing.
ALLOWED = {"docs/ui-development.md": 1}


@pytest.mark.reads_the_repo  # reads the prose out of this checkout
def test_the_docs_tell_a_user_to_type_hp_not_uv_run_hp() -> None:
    """Outside the one dev-loop command, no document tells a reader to type `uv run hp`."""
    counts = {str(path.relative_to(ROOT)): path.read_text().count("uv run hp") for path in DOCS}
    assert {doc: count for doc, count in counts.items() if count} == ALLOWED
