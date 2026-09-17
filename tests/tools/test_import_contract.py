"""The layers contract goes red when it is loosened or the tree breaks it.

`mise run lint-imports` holds `src/hyphae` to `[tool.importlinter]` in `pyproject.toml`, and a
green run says only that today's tree keeps today's contract. What these leaves add is that
the gate can go red at all: that a lifted layer names the edge that now points up, and that
`exhaustive` names a module no line claims. Each case rewrites the real contract rather than
pinning a copy, so a layer added later is still the one under test.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.tools.conftest import contract_layers

ROOT = Path(__file__).resolve().parents[2]


def peer_line(layers: list[str], peers: set[str]) -> int:
    """The index of the line holding exactly these peers, in whichever order it spells them."""
    holding = [at for at, layer in enumerate(layers) if set(layer.split(" | ")) == peers]
    assert holding, f"{sorted(peers)} no longer share a line; retarget this case"
    (at,) = holding
    return at


def store_above_view(layers: list[str]) -> list[str]:
    """`store` lifted off its line to above `view | enrich`, so every import of it points up."""
    holding = [layer for layer in layers if "store" in layer.split(" | ")]
    assert holding, "no line holds `store`; retarget this case"
    (line,) = holding
    peers = [name for name in line.split(" | ") if name != "store"]
    layers = [
        (" | ".join(peers) if layer == line else layer)
        for layer in layers
        if layer != line or peers
    ]
    at = layers.index("view | enrich")
    return [*layers[:at], "store", *layers[at:]]


def without_user_settings(layers: list[str]) -> list[str]:
    """The `user_settings` line dropped, so the exhaustive contract has a module no line claims."""
    assert "user_settings" in layers, "`user_settings` has left the contract; retarget this case"
    return [layer for layer in layers if layer != "user_settings"]


def enrich_above_view(layers: list[str]) -> list[str]:
    """`enrich` lifted onto its own line above `view`: strictly tighter than `view | enrich`.

    The shipped line says neither imports the other; this says `view` may not import `enrich`
    while `enrich` could import `view`. Kept green, it is the lasting proof that the viewer
    reads the enrichment vocabulary from `models` and nothing from `enrich`.
    """
    at = peer_line(layers, {"view", "enrich"})
    return [*layers[:at], "enrich", "view", *layers[at + 1 :]]


def store_above_extract(layers: list[str]) -> list[str]:
    """`store` lifted onto its own line above `extract`: strictly tighter than `store | extract`.

    The shipped line says neither imports the other; this says `extract` may not import `store`
    while `store` could import `extract`. Kept green, it is the lasting proof that the parser
    reaches no store: transcripts in, `SessionTrace` out, and no database on the way.
    """
    at = peer_line(layers, {"store", "extract"})
    return [*layers[:at], "store", "extract", *layers[at + 1 :]]


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
        # Uncached for the reason `mise.toml` gives: a stale variant would red the wrong edge.
        ["uv", "run", "lint-imports", "--no-cache", "--config", str(path)],
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
        (store_above_view, "hyphae.view is not allowed to import hyphae.store"),
        (without_user_settings, "hyphae.user_settings"),
    ],
    ids=["store_lifted_above_view", "user_settings_line_dropped"],
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


@pytest.mark.reads_the_repo  # the same subprocess, over a contract tighter than the one written
def test_the_viewer_imports_nothing_from_enrich(tmp_path: Path) -> None:
    # If `enrich` is lifted above `view`, so that only `view -> enrich` would break it...
    done = run_contract(enrich_above_view(contract_layers()), tmp_path)
    # ...the contract is still kept: no page, part or fetch reaches into the enrichment pass.
    assert done.returncode == 0, done.stdout
    assert "Contracts: 1 kept, 0 broken" in done.stdout


@pytest.mark.reads_the_repo  # the same subprocess, over a contract tighter than the one written
def test_the_parser_imports_nothing_from_store(tmp_path: Path) -> None:
    # If `store` is lifted above `extract`, so that only `extract -> store` would break it...
    done = run_contract(store_above_extract(contract_layers()), tmp_path)
    # ...the contract is still kept: no extractor opens, reads or names the trace store.
    assert done.returncode == 0, done.stdout
    assert "Contracts: 1 kept, 0 broken" in done.stdout


@pytest.mark.reads_the_repo  # the same subprocess, over the contract as written
def test_the_contract_as_written_is_kept(tmp_path: Path) -> None:
    # The control: the rewrite itself is faithful, so a red case above is the change and not
    # the scratch config. `mise run lint-imports` runs the real file; this runs its copy.
    done = run_contract(contract_layers(), tmp_path)
    assert done.returncode == 0, done.stdout
    assert "Contracts: 1 kept, 0 broken" in done.stdout
