"""The layers contract goes red when it is loosened or the tree breaks it.

`mise run lint-imports` holds `src/hyphae` to `[tool.importlinter]` in `pyproject.toml`, and a
green run says only that today's tree keeps today's contract. What these leaves add is that
the gate can go red at all: that a layer swap names the edge that now points up, and that
`exhaustive` names a module no line claims. Each case rewrites the real contract rather than
pinning a copy, so a layer added later is still the one under test.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.tools.conftest import contract_layers

ROOT = Path(__file__).resolve().parents[2]


def swapped(layers: list[str]) -> list[str]:
    """`export` moved above `extract`, so `extract -> export` points up."""
    extract, export = layers.index("extract"), layers.index("export")
    assert extract < export, "`extract` no longer sits above `export`; retarget this case"
    layers = list(layers)
    layers[extract], layers[export] = layers[export], layers[extract]
    return layers


def without_user_settings(layers: list[str]) -> list[str]:
    """The `user_settings` line dropped, so the exhaustive contract has a module no line claims."""
    assert "user_settings" in layers, "`user_settings` has left the contract; retarget this case"
    return [layer for layer in layers if layer != "user_settings"]


def run_contract(layers: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """`lint-imports` over the real package, under a contract rewritten to these layers.

    Written in import-linter's `.ini` dialect: it reads TOML only from a `[tool.importlinter]`
    table, and the `.ini` form lists layers one per line, so a swap or a drop is that list
    changing and nothing else.
    """
    path = tmp_path / "importlinter.ini"
    path.write_text(
        "[importlinter]\nroot_package = hyphae\n\n"
        "[importlinter:contract:layers]\nname = Layers\ntype = layers\ncontainers = hyphae\n"
        "exhaustive = true\nlayers =\n" + "".join(f"    {layer}\n" for layer in layers)
    )
    return subprocess.run(
        ["uv", "run", "lint-imports", "--config", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


# One subprocess over the whole package per case: the contract's only observable seam is the
# exit code and the report, which no in-process call reaches. Not `slow`: grimp reads the
# package in well under a second.
@pytest.mark.reads_the_repo  # runs `lint-imports` over `src/hyphae` from the checkout
@pytest.mark.parametrize(
    ("loosen", "named"),
    [
        (swapped, "hyphae.extract is not allowed to import hyphae.export"),
        (without_user_settings, "hyphae.user_settings"),
    ],
    ids=["export_swapped_above_extract", "user_settings_line_dropped"],
)
def test_a_loosened_contract_goes_red_and_names_what_broke(
    loosen: Callable[[list[str]], list[str]], named: str, tmp_path: Path
) -> None:
    # If we take the real contract and change one thing about it...
    layers = loosen(contract_layers())
    # ...the run is red rather than a kept contract with a different shape...
    done = run_contract(layers, tmp_path)
    assert done.returncode != 0, done.stdout
    # ...and the report names the packages whose edge now points up, or the module no line
    # claims.
    assert named in done.stdout, done.stdout


@pytest.mark.reads_the_repo  # the same subprocess, over the contract as written
def test_the_contract_as_written_is_kept(tmp_path: Path) -> None:
    # The control: the rewrite itself is faithful, so a red case above is the change and not
    # the scratch config. `mise run lint-imports` runs the real file; this runs its copy.
    done = run_contract(contract_layers(), tmp_path)
    assert done.returncode == 0, done.stdout
    assert "Contracts: 1 kept, 0 broken" in done.stdout
