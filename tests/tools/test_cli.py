"""What a cog block actually runs: `uv run python -m tools.gen_<name>`, out of the repository root.

Every other leaf in this tier calls `generate()` in-process, which says nothing about the seam
the document depends on — a module that cannot be run, or a `main()` that prints something
other than what it generated, would splice a broken block with the whole suite green. So these
run the command for real and compare its stdout to the text the generator returns.
"""

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tools import gen_bounds, gen_imports, gen_layout, gen_routes, gen_schema

ROOT = Path(__file__).resolve().parents[2]
# A live cog marker: the command a document runs, with the fence-wrapped example in
# `docs/documentation.md` and the plan snapshots under `plans/` left out below.
MARKER = re.compile(r'<!-- aigarden:cog sh "uv run python -m tools\.(gen_\w+)')

# One invocation per generator, each with the text it should have printed. The two generators
# that take an argument are asked for one table: the argument handling is what is under test
# here, not every table, which the generators' own tiers cover.
COMMANDS: list[tuple[str, tuple[str, ...], Callable[[], str]]] = [
    ("gen_routes", (), gen_routes.generate),
    ("gen_bounds", ("knobs",), lambda: gen_bounds.generate(gen_bounds.Table.KNOBS)),
    ("gen_layout", (), gen_layout.generate),
    ("gen_schema", ("identity",), lambda: gen_schema.generate(gen_schema.Section.IDENTITY)),
    ("gen_imports", (), gen_imports.generate),
]


def run(module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """One generator, run the way a cog block runs it."""
    return subprocess.run(
        ["uv", "run", "python", "-m", f"tools.{module}", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("module", "arguments", "generated"), COMMANDS, ids=[name for name, _, _ in COMMANDS]
)
def test_the_command_a_cog_block_runs_prints_what_the_generator_returns(
    module: str, arguments: tuple[str, ...], generated: Callable[[], str]
) -> None:
    # The whole contract of the CLI seam: exit 0, and the generated body on stdout with the one
    # newline `print` adds. A block spliced from anything else would drift from these tests.
    done = run(module, *arguments)
    assert done.returncode == 0, done.stderr
    assert done.stdout == generated() + "\n"


def test_a_generator_asked_for_no_table_says_which_ones_it_has() -> None:
    # The other half of the seam. A cog block whose argument is missing or misspelled has to
    # fail loudly, because the alternative is a document splicing an empty block.
    done = run("gen_bounds")
    assert done.returncode != 0
    assert "knobs" in done.stderr and "bounds" in done.stderr


def live_markers(document: Path) -> set[str]:
    """The generators a document's cog markers name, a marker inside a fence left out."""
    named = set()
    fenced = False
    for line in document.read_text().splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and (match := MARKER.match(line)):
            named.add(match[1])
    return named


# Generators under `tools/` that no cog block runs, each with why; anything else there must be.
NOT_SPLICED = {
    "gen_e2e_routes": "writes `tests/e2e/routes.json` for Playwright; its own leaf compares bytes",
}


@pytest.mark.reads_the_repo  # walks `tools/` and every document in the checkout
def test_every_generator_is_run_by_a_live_cog_block() -> None:
    """A generator in `tools/` is named by a cog marker some document splices, or says why not."""
    # If we take every `gen_*.py` under `tools/` that is not excused above...
    generators = {path.stem for path in (ROOT / "tools").glob("gen_*.py")}
    assert set(NOT_SPLICED) <= generators, "an excuse outlived the generator it excused"
    spliced = generators - set(NOT_SPLICED)
    assert spliced >= {name for name, _, _ in COMMANDS}
    # ...and every marker outside a fence in a document of the checkout — a new one included,
    # so the leaf is green before the commit that adds it — that is not a plan's snapshot...
    tracked = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    documents = [ROOT / path for path in tracked if not path.startswith("plans/")]
    wired = set().union(*(live_markers(path) for path in documents))
    # ...then each generator has a block that runs it, so `cogs-check` holds its output live —
    # a generator no document names is one whose drift nothing would catch.
    assert spliced <= wired, f"generators no live cog block runs: {sorted(spliced - wired)}"
