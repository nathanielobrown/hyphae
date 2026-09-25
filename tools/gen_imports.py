"""The package graph in `docs/layering.md`: which child of `hyphae` imports which, from grimp.

Run by a cog block in that file — `uv run python -m tools.gen_imports` — and it writes the
fence as well as the graph, because a cog marker inside a fence is an example rather than a
live block. An arrow runs from the importer to what it imports.
"""

import itertools

import grimp

from tools import text

ROOT_PACKAGE = "hyphae"

# Left off the graph: `cli`, which imports every package, and the leaves any package may import
# — the layers contract's top line and bottom two. A test holds this set to those lines.
OMITTED = frozenset(
    {"cli", "user_settings", "models", "projects", "pricing", "settings", "store_path"}
)


def edges() -> list[tuple[str, str]]:
    """Every `(importer, imported)` pair among the drawn children, sorted, by short name."""
    graph = grimp.build_graph(ROOT_PACKAGE)
    drawn = sorted(
        child.removeprefix(f"{ROOT_PACKAGE}.")
        for child in graph.find_children(ROOT_PACKAGE)
        if child.removeprefix(f"{ROOT_PACKAGE}.") not in OMITTED
    )
    return [
        (importer, imported)
        for importer, imported in itertools.permutations(drawn, 2)
        if graph.direct_import_exists(
            importer=f"{ROOT_PACKAGE}.{importer}",
            imported=f"{ROOT_PACKAGE}.{imported}",
            as_packages=True,
        )
    ]


def generate() -> str:
    """The graph as the cog block splices it, fence and all."""
    lines = [f"  {importer} --> {imported}" for importer, imported in edges()]
    return text.fence("mermaid", ["graph TD", *lines])


def main() -> None:
    print(generate())


if __name__ == "__main__":
    main()
