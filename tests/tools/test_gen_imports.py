"""What the package graph in `docs/layering.md` has to hold: every real edge, and only those.

The oracle is a regex sweep of the source for `hyphae.` imports, not grimp, so a generator
that misread grimp's API and a grimp release that changed it both show.
"""

import pkgutil
import re
from pathlib import Path

import pytest

import hyphae
from tests.tools.conftest import contract_layers
from tools import gen_imports

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "hyphae"

# One import of a sibling under `hyphae`, in either spelling the package uses.
IMPORT = re.compile(r"^\s*(?:from hyphae\.(\w+)|import hyphae\.(\w+)|from hyphae import (\w+))")


def swept_edges() -> set[tuple[str, str]]:
    """Every `(importer, imported)` pair between children of `hyphae`, read from the source."""
    edges = set()
    for path in PACKAGE.rglob("*.py"):
        importer = path.relative_to(PACKAGE).parts[0].removesuffix(".py")
        for line in path.read_text().splitlines():
            if match := IMPORT.match(line):
                imported = next(group for group in match.groups() if group)
                if imported != importer:
                    edges.add((importer, imported))
    return edges


def drawn_edges(graph: str) -> set[tuple[str, str]]:
    """Every `a --> b` line of the generated graph, as a pair."""
    return {
        (match[1], match[2])
        for line in graph.splitlines()
        if (match := re.fullmatch(r"\s+(\w+) --> (\w+)", line))
    }


@pytest.fixture(scope="module")
def graph() -> str:
    return gen_imports.generate()


@pytest.mark.reads_the_repo  # sweeps `src/hyphae` as text
def test_every_drawn_edge_is_a_real_import_and_every_real_one_is_drawn(graph: str) -> None:
    # If we sweep the source for imports between the children of `hyphae`, and drop every edge
    # that touches a node the diagram leaves off...
    expected = {
        (importer, imported)
        for importer, imported in swept_edges()
        if importer not in gen_imports.OMITTED and imported not in gen_imports.OMITTED
    }
    # ...then the diagram draws exactly those — no edge invented, none dropped.
    assert drawn_edges(graph) == expected
    # And there is something to compare: an empty sweep would pass an empty diagram.
    assert expected


def test_every_omission_names_a_module_hyphae_still_has() -> None:
    # A suppression outlives what it suppressed unless something says otherwise: a module that
    # leaves the package takes its line here with it. `cli` is the one the convention names.
    children = {module.name for module in pkgutil.iter_modules(hyphae.__path__)}
    assert set(gen_imports.OMITTED) <= children
    assert "cli" in gen_imports.OMITTED


def test_the_omitted_modules_are_the_contracts_top_line_and_bottom_two() -> None:
    # The omissions are the contract's ends and nothing else: the entry point above every
    # package, and the leaves below every one. Filtering the sweep by `OMITTED` alone would let
    # a leaf dropped from the set draw its fan of arrows and pass, so the set is pinned here.
    layers = contract_layers()
    ends = [layers[0], *layers[-2:]]
    assert set(gen_imports.OMITTED) == {name.strip() for line in ends for name in line.split("|")}


def test_the_layers_the_plan_drew_are_the_ones_the_graph_shows(graph: str) -> None:
    """The store is what every package reaches, and the parser reaches no store: `extract` and
    `store` each import only the pipeline seam, nothing imports either of them or `export`, the
    pass reads and writes its tables through `store`, and the viewer reads the enrichment
    vocabulary from `models` rather than from the pass."""
    edges = drawn_edges(graph)
    # The reader rebuilds a trace from rows as a `SessionSource`, so the store's one edge is
    # the seam, and the parser's is the same one: neither reaches the other...
    assert {edge for edge in edges if edge[0] == "store"} == {("store", "pipeline")}
    assert {edge for edge in edges if edge[0] == "extract"} == {("extract", "pipeline")}
    # ...the enrichment tables' writer sits in `store`, so the pass points down at it...
    assert ("enrich", "store") in edges
    # ...no package imports the exporter or the parser to reach the store...
    assert not [edge for edge in edges if edge[1] in ("export", "extract")]
    # ...the edge phase 1 removed stays gone: `view` and `enrich` share a layer line...
    assert ("view", "enrich") not in edges
    # ...and so does the one phase 3 cut: the viewer binds its widths and lists its statements
    # through the library, so it reads nothing from the analysis layer.
    assert ("view", "analyze") not in edges


def test_each_edge_is_one_unlabelled_arrow(graph: str) -> None:
    # Every body line is `importer --> imported` and nothing else: no label, no comment, no
    # style — the convention the overview's hand-drawn diagrams follow.
    body = graph.strip().splitlines()[2:-1]
    assert body, graph
    for line in body:
        assert re.fullmatch(r"\s+\w+ --> \w+", line), line
    # And the order is fixed, so a regenerate that changed nothing writes nothing.
    assert body == sorted(body)


def test_the_graph_is_fenced_with_a_blank_line_either_side(graph: str) -> None:
    # The fence is inside the cog block, because a marker inside a fence is an example rather
    # than a live block — so the generator owns both fence lines and the blank lines that keep
    # them off the markers, which aigarden's MD031 asks for. `print` adds the closing newline.
    assert graph.startswith("\n```mermaid\ngraph TD\n")
    assert graph.endswith("\n```\n")
