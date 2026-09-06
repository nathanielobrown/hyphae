"""The tree the viewer's modules live in, which no rendered page can show.

`src/hyphae/view/` is organized by page and then by kind (`plans/view-layout/design.md`): one
package per page, the same file names inside each, and a shared layer under them all. The
layout is the contract — it is what makes "the context for one page is one directory" true —
and nothing but this file holds it. Each leaf reads the checkout the way
`tests/view/test_components.py` reads the components package's rules: `ast` over the source,
plus a fresh-interpreter probe where an in-process answer is already spoiled.

Every scan carries a companion assertion. A rule that finds nothing passes, and a tree that
moved out from under it is exactly how it comes to find nothing.
"""

import ast
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

import hyphae.view
from hyphae.analyze import queries
from tests.view import test_components

PACKAGE = "hyphae.view"
QUERIES = "hyphae.analyze.queries"
VIEW = Path(hyphae.view.__file__).parent
PAGES = VIEW / "pages"
TEXT = VIEW / "text"

# One package per page the glossary names (`CONTEXT.md`, "Viewer pages"). The node page is one
# package for the three route modules that serve it, and the two lists are one page each.
PAGE_NAMES = frozenset({"projects", "sessions", "node", "errors", "query", "records", "offload"})

# How one value prints, and nothing else — the seven modules `text/` gathers.
TEXT_MODULES = frozenset(
    {"format", "cuts", "labels", "tool_names", "render", "highlight", "inline_markdown"}
)

# The two file names that say what kind a module of a page package is, each of which may be a
# module or a package: a page small enough writes `routes.py`, and the node page needs `routes/`.
KINDS = ("routes", "markup")

# The names a page gives the modules that read the store for it, on the far side of the seam
# from its markup (`plans/deepen-viewer-reads/design.md`). A page small enough has one `read.py`;
# the node page names its two for what they do — `browser.py` for the documents, `fragments.py`
# for the small fetches under them.
READS = frozenset({"read", "browser", "fragments"})

# What a value crossing that seam may not be made of: a request, a response, or an element.
# The store is banned by name below rather than listed here — `duckdb` is not what a raw row
# arrives as, `view.store.Row` is.
FRAMEWORKS = frozenset({"fastapi", "starlette", "htpy"})

# Names that say nothing about what a module builds. A presenter is named for the thing it
# makes — `nav_tree.py`, `walk.py` — and these are where the unnamed leftovers collect.
UNNAMED = frozenset({"logic.py", "utils.py", "helpers.py", "common.py", "misc.py"})

# What a module may reach: an import goes down a layer or sideways, never up. The layers, from
# the top: the server, then the pages, then what every page shares, then the store, and under
# all of it the two leaves — how one value prints, and the sizes it prints to. `bounds` is a
# leaf beside `text/` rather than above it because `highlight` and `inline_markdown` read their
# cuts from it, and a cut is a size (`design.md`, "Decisions").
SERVER, PAGE, SHARED, BASE, LEAF = 4, 3, 2, 1, 0

# The one number `analyze/queries.py` declares that is not a size: the keyset cursor standing
# before the first row, which a paged route takes as its default rather than cutting to it.
NOT_A_SIZE = frozenset({"FIRST_PAGE"})

# What a routes module may still take from the store: the words a session-list URL is written
# in. A route's job is to refuse a URL, and refusing `?sort=banana` means holding the list of
# sorts (`view/store.py`). Everything else the store exports is a query, a binding or a row.
URL_WORDS = frozenset({"SORTS", "FILTERS", "DIRECTIONS"})

# And what it may still take from the query library: the cursor above, plus the two names for
# what a URL word is once it is parsed. The session list's filters arrive as text and are bound
# to the types `FILTERS` declares; the refusal for text that will not bind is a 400, which only
# a routes module raises, so the parse stays there and the types it reads and produces with it.
BINDABLE = frozenset({"ParamType", "ParamValue"})

# The modules of each layer by name, for the ones that are not decided by their directory. The
# top level has no default: a module that lands there and is not listed reds `layer()`, because
# guessing a layer for it is how an edge nobody meant to allow becomes sideways and legal.
LAYERED = {
    "app": SERVER,
    "dev": SERVER,
    # Under every page rather than one page's: the `Viewer`, a request's read-only connection,
    # and `checked`. Shared is also what makes an import of a page from here point up and red.
    "deps": SHARED,
    "nodes": SHARED,
    "enrichment": SHARED,
    "citation": SHARED,
    "links": SHARED,
    "failures": SHARED,
    "builders": SHARED,
    "detail": SHARED,
    "store": BASE,
    "manifest": BASE,
    "bounds": LEAF,
}

# Import the named modules in a fresh interpreter and report which web frameworks came in with
# them. A list built from the tree rather than written down, so a presenter that lands next year
# is covered without anyone remembering this file.
PROBE = """
import importlib, sys
for name in {names!r}:
    importlib.import_module(name)
sys.stdout.write(",".join(sorted({{"fastapi", "starlette"}} & set(sys.modules))))
"""


def sources(root: Path) -> list[Path]:
    """Every module under one directory of the package, or none where it does not exist yet."""
    return sorted(root.rglob("*.py")) if root.is_dir() else []


def dotted(path: Path) -> str:
    """The module one file is, as its dotted name inside `hyphae.view`.

    A package's `__init__.py` is the package itself, so an import of `components` and an import
    of `components/__init__.py`'s own name read as the same node of the graph.
    """
    parts = path.relative_to(VIEW).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def exists(module: str) -> bool:
    """Whether a dotted name under `hyphae.view` is a module or a package on the tree."""
    at = VIEW / Path(*module.split("."))
    return at.with_suffix(".py").is_file() or (at / "__init__.py").is_file()


def named(path: Path) -> set[str]:
    """Every top-level package one file imports, whatever it took from it."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            found.add(node.module.split(".")[0])
    return found


def imports(path: Path) -> set[str]:
    """Every module inside `view/` that one file imports, by dotted name.

    `from hyphae.view import format as fmt` names a module and `from hyphae.view.components
    import Html` names a package, so each imported name is resolved against the tree and falls
    back to the package it was taken from. Absolute imports only: relative ones are banned
    repo-wide (`pyproject.toml`, `flake8-tidy-imports`).
    """
    here = dotted(path)
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {
                alias.name.removeprefix(PACKAGE).lstrip(".")
                for alias in node.names
                if alias.name == PACKAGE or alias.name.startswith(f"{PACKAGE}.")
            }
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module != PACKAGE and not node.module.startswith(f"{PACKAGE}."):
                continue
            base = node.module.removeprefix(PACKAGE).lstrip(".")
            for alias in node.names:
                named = f"{base}.{alias.name}" if base else alias.name
                found.add(named if exists(named) else base)
    # A module reaching into itself is not an edge, and neither is the package root, which
    # holds a docstring and nothing to import.
    return {name for name in found if name and name != here}


def taken(path: Path, module: str) -> set[str]:
    """Every name one file imports out of one module of the viewer, by that module's own name."""
    return {
        alias.name
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom) and node.module == f"{PACKAGE}.{module}"
        for alias in node.names
    }


def queried(path: Path) -> set[str]:
    """Every name one file takes from the query library, by attribute or by import."""
    tree = ast.parse(path.read_text())
    found = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "queries"
    }
    return found | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == QUERIES
        for alias in node.names
    }


def edges() -> set[tuple[str, str]]:
    """Every import inside `view/`, as the pair `(importer, imported)`."""
    return {(dotted(path), name) for path in sources(VIEW) for name in imports(path)}


def layer(module: str) -> int:
    """Which layer one module of `view/` sits on."""
    head = module.split(".", maxsplit=1)[0]
    if head == "text":
        return LEAF
    if head == "components":
        return SHARED
    if head == "pages":
        return PAGE
    assert module in LAYERED, f"`view/{module}.py` sits at the top level and names no layer"
    return LAYERED[module]


def page_packages() -> list[Path]:
    """Every page package on the tree, discovered rather than listed.

    A directory of `pages/` and not any package under one: the node page holds a `routes/` and a
    `markup/` of its own, and those are kinds of that page rather than pages beside it. Every
    directory, not every package — a page that lost its `__init__.py` would otherwise drop out
    of the discovery instead of failing it.
    """
    return sorted(at for at in PAGES.iterdir() if at.is_dir() and not at.name.startswith("_"))


def kind_of(page: Path, path: Path) -> str:
    """Which kind of module of its page a file is: `routes`, `markup`, or a presenter's name."""
    head = path.relative_to(page).parts[0]
    return head.removesuffix(".py")


def markup_modules() -> list[Path]:
    """Every module of markup a page holds, whether it writes a `markup.py` or a `markup/`.

    A `markup/` package's `__init__.py` is left out the way `test_components.py:MODULES` leaves
    the components package's out: it says what the package is and defines no component.
    """
    return [
        path
        for page in page_packages()
        for path in sources(page)
        if kind_of(page, path) == "markup" and path.name != "__init__.py"
    ]


def read_modules() -> list[Path]:
    """Every module of a page that reads the store for it, whatever the page named it."""
    return [
        path
        for page in page_packages()
        for path in sources(page)
        if kind_of(page, path) in READS and path.name != "__init__.py"
    ]


def model_modules() -> list[Path]:
    """Every page's neutral model module — the typed value its read hands its markup."""
    return [path for path in sources(PAGES) if path.name == "models.py"]


def frameworks(names: Sequence[str]) -> str:
    """The web frameworks a fresh interpreter importing `names` ended up holding."""
    done = subprocess.run(
        [sys.executable, "-c", PROBE.format(names=list(names))],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return done.stdout


# --- Rule 1: what a file's name says about what is inside it -------------------------------


def test_every_page_the_viewer_serves_has_a_package_of_its_own() -> None:
    """The pages the glossary names are the packages on the tree, one for one.

    The companion every leaf below leans on: each of them is parametrized over what `iterdir`
    finds, so a `pages/` that emptied or moved would leave them all passing on nothing. This is
    the leaf that says the discovery found the viewer.
    """
    found = page_packages()
    assert {page.name for page in found} == set(PAGE_NAMES)
    # And each is a package, which is what the leaves below import it by.
    assert [page.name for page in found if not (page / "__init__.py").is_file()] == []


@pytest.mark.parametrize("page", page_packages(), ids=lambda page: page.name)
def test_only_a_pages_routes_module_reaches_a_web_framework(page: Path) -> None:
    """A presenter is callable without a request, so pyrefly rather than FastAPI owns its types.

    A fresh interpreter, because this tier's conftest builds `TestClient`s: by the time any test
    runs `fastapi` is in `sys.modules`, and an in-process assertion would pass on a presenter
    importing `Request` on its first line.
    """
    routes = [path for path in sources(page) if kind_of(page, path) == "routes"]
    rest = [path for path in sources(page) if kind_of(page, path) != "routes"]
    # The page has both halves to tell apart...
    assert routes, f"{page.name} declares no routes"
    assert rest, f"{page.name} is nothing but routes"
    # ...nothing but the routes reaches a framework...
    assert frameworks([f"{PACKAGE}.{dotted(path)}" for path in rest]) == ""
    # ...and the routes do, which is what shows the probe can see a framework at all.
    assert frameworks([f"{PACKAGE}.{dotted(path)}" for path in routes]) == "fastapi,starlette"


@pytest.mark.parametrize("page", page_packages(), ids=lambda page: page.name)
def test_every_page_package_holds_one_routes_kind_and_one_markup_kind(page: Path) -> None:
    """`routes.py` or `routes/`, `markup.py` or `markup/`, one of each and never both.

    The consistency the tree is for: an agent looking for where a page answers a request opens
    the file whose name says so, without listing the directory first.
    """
    for kind in KINDS:
        module = (page / f"{kind}.py").is_file()
        package = (page / kind / "__init__.py").is_file()
        assert module != package, f"{page.name}: {kind}.py={module} {kind}/={package}"


def test_only_a_markup_module_imports_htpy() -> None:
    """Markup is written in one file of a page, so a change to what a page shows has one home."""
    naming = {path for path in sources(VIEW) if "htpy" in named(path)}
    # The scan found markup...
    assert naming, "no module in the viewer imports htpy"
    # ...every page's markup writes some...
    assert set(markup_modules()) <= naming
    # ...and nothing else in the package names htpy at all, shared layer included: the whole
    # viewer is read, so a new top-level module writing markup reds here rather than escaping.
    assert naming <= set(test_components.SOURCES)


def test_no_module_of_a_page_is_named_for_nothing() -> None:
    """A presenter is named for what it builds; these five names are where leftovers collect.

    The checkable floor under rule 1. That `nav_tree.py` is a better name than `logic.py` for
    what is in it is a judgement about English, and review owns it (`.claude/rules/viewer-ui.md`).
    """
    found = sources(PAGES)
    # There are modules to read...
    assert found, "`pages/` holds no module"
    # ...and none of them took one of the names that says nothing.
    assert [str(path.relative_to(VIEW)) for path in found if path.name in UNNAMED] == []


def test_a_models_module_stands_between_its_pages_read_and_its_markup() -> None:
    """A page model is the typed value one page's read hands its own markup, and nothing else.

    It earns its file by having two readers on opposite sides of a seam
    (`plans/deepen-viewer-reads/design.md`, "Put models at the new seam"). A model only the
    markup reads belongs beside the markup, and a model only the read builds is not a model —
    so both halves are asserted, and a third page reaching for one is already forbidden by
    `test_no_page_package_imports_a_sibling_page`.
    """
    found = model_modules()
    # There are page models to read...
    assert found, "no page declares a `models.py`, so this rule holds nothing"
    for path in found:
        page = path.parent
        here = dotted(path)
        # ...each is built by the read on one side of the seam...
        assert [
            module
            for module in read_modules()
            if module.is_relative_to(page) and here in imports(module)
        ], f"{path.relative_to(VIEW)} is built by no read module of its page"
        # ...and read by the markup on the other.
        assert [
            module
            for module in markup_modules()
            if module.is_relative_to(page) and here in imports(module)
        ], f"{path.relative_to(VIEW)} is read by no markup module of its page"


def test_a_page_model_is_made_of_nothing_either_side_of_the_seam_owns() -> None:
    """The value that crosses is neutral: no request, no response, no element, no raw row.

    What makes the seam worth having. A model carrying a `Request` would put FastAPI on the
    markup's side of it, and one carrying a `Row` would leave the raw store columns to be
    indexed by whoever prints them. Typed citations are not on this list: evidence is part of
    what the read produced.
    """
    found = model_modules()
    # There are page models to read...
    assert found, "no page declares a `models.py`, so this rule holds nothing"
    for path in found:
        assert not named(path) & FRAMEWORKS, f"{path.relative_to(VIEW)} names a framework"
        assert "Row" not in taken(path, "store"), f"{path.relative_to(VIEW)} carries a store row"
    # ...and the scan can see such a name where one is: every page's markup names htpy.
    assert all("htpy" in named(path) for path in markup_modules())


def test_a_pages_markup_never_reads_back_across_the_seam() -> None:
    """Markup takes the model it is given; it does not reach into the read for a second row.

    The direction is the whole point of the split: a markup module that imported its page's
    read could open the store while a page renders, which is the window `deps.py` closes.
    """
    found = read_modules()
    # There are read modules to reach back into...
    assert found, "no page declares a read module"
    for path in found:
        page = path.parent
        here = dotted(path)
        # ...and no markup of their own pages does.
        assert [
            module
            for module in markup_modules()
            if module.is_relative_to(page) and here in imports(module)
        ] == [], f"markup of {page.name} imports {here}"


def test_no_routes_module_of_a_page_names_the_stores_vocabulary() -> None:
    """A route holds a URL and a refusal; what a query is, what it binds and what it answers
    stops in the read.

    The other half of the seam. `test_only_a_pages_routes_module_reaches_a_web_framework` keeps
    FastAPI out of the reads, and this keeps the store out of the routes — without it a page
    can pass both directions of the model rule and still run its query beside its endpoint,
    which is the window `deps.py` exists to close.

    `Db` stays legal, because a fragment's lock window is deliberate (`view/deps.py`): what is
    banned is the query member, the bindings and the raw row, not the connection they run on.
    """
    found = [
        path
        for page in page_packages()
        for path in sources(page)
        if kind_of(page, path) == "routes"
    ]
    # There are routes to read...
    assert found, "no page declares a routes module"
    for path in found:
        names = taken(path, "store")
        # ...none of them takes the store module whole, which would hide the names below...
        assert "store" not in imports(path) or names, f"{dotted(path)} imports the store whole"
        # ...none names anything the store exports but the words a URL is written in...
        assert names <= URL_WORDS, f"{dotted(path)} names the store's {sorted(names - URL_WORDS)}"
        # ...and none names a query the library declares.
        asked = queried(path)
        assert asked <= NOT_A_SIZE | BINDABLE, f"{dotted(path)} names the library's {sorted(asked)}"
    # ...and the scan can see that vocabulary where it belongs: the reads run the queries.
    ran = {name for path in read_modules() for name in taken(path, "store")}
    assert {"page_rows", "bound"} <= ran


# --- Rule 2: a page package is a leaf ------------------------------------------------------


def test_no_page_package_imports_a_sibling_page() -> None:
    """One page is one directory, so what two pages share is lifted rather than reached for.

    `failures.py` and the session header's widths were lifted into the shared layer for this
    (`design.md`, "Three lifts"): a session's failures are a session fact the errors page and
    the node page's stepper both read, and a sibling import would make the errors page the node
    page's dependency.
    """
    found = [(dotted(path), name) for path in sources(PAGES) for name in imports(path)]
    # There are page modules importing something...
    assert found, "no module under `pages/` imports anything inside the viewer"
    for importer, imported in found:
        page = importer.split(".")[1]
        assert not (imported.startswith("pages.") and imported.split(".")[1] != page), (
            f"{importer} → {imported}"
        )


# --- Rule 3: downward only -----------------------------------------------------------------


def test_no_import_inside_the_viewer_points_up_a_layer() -> None:
    """The layers hold: pages over the shared view-models, over the store, over `text/`.

    What keeps the shared layer readable without the pages and testable without a request. The
    failure prints the edge, because an edge is what has to be deleted to fix it.
    """
    found = edges()
    # The graph found the package...
    assert found, "no import inside the viewer was resolved"
    # ...including the edge this whole tree is built around: a presenter reading the node model.
    assert any(
        imported == "nodes" and importer.split(".")[-1] == "walk" for importer, imported in found
    )
    # ...and every edge in it goes down a layer or sideways.
    for importer, imported in sorted(found):
        assert layer(imported) <= layer(importer), f"{importer} → {imported}"


def test_text_reaches_nothing_in_the_viewer_but_itself_and_the_sizes_it_cuts_to() -> None:
    """`text/` is the leaf of the package: how one value prints, and nothing above it.

    `bounds` is the one exception the design takes, and it is the same kind of thing: a cut is
    a size, and `highlight` and `inline_markdown` read theirs from it.
    """
    found = sources(TEXT)
    # The seven printing modules are there to be read...
    assert {path.stem for path in found} - {"__init__"} == set(TEXT_MODULES)
    # ...and not one of them reaches past itself.
    for path in found:
        for name in imports(path):
            assert name == "bounds" or name.split(".")[0] == "text", f"{dotted(path)} → {name}"


def test_no_module_of_the_viewer_but_bounds_names_a_size_the_query_library_declares() -> None:
    """A width is the surface's, so `bounds.py` is the one place the viewer names a number.

    `bounds.py` reads one off the library itself: the two timelines behind a children log
    declare `LOG_CHARS` as their own default (`analyze/manifest.py`), which makes it a query's
    number that a surface reads rather than a viewer width the library holds. Everything else
    the viewer takes from that module is a type, a loader or a sentinel.
    """
    taken = {(dotted(path), name) for path in sources(VIEW) for name in queried(path)}
    sizes = {
        (where, name)
        for where, name in taken
        if name not in NOT_A_SIZE and isinstance(getattr(queries, name), int)
    }
    # The scan reaches the library at all...
    assert ("bounds", "LOG_CHARS") in sizes
    # ...and nothing but the sizes leaf takes a number from it.
    assert {where for where, _ in sizes} == {"bounds"}


def test_the_shared_node_model_reads_nothing_from_a_page() -> None:
    """`nodes.py` is under every page, so an import of a page's own module inverts the tree.

    Named rather than left to the graph above because this is where a cycle comes back
    silently: the icons moved into `nodes.GLYPHS` to delete one such edge, and the move is only
    real while the edge stays gone.
    """
    reached = imports(VIEW / "nodes.py")
    # The model still imports what it is built on...
    assert reached, "`nodes` imports nothing inside the viewer"
    # ...and nothing that a page owns.
    assert [name for name in reached if layer(name) >= PAGE] == []


# --- Rule 4: the components rules cover a page's markup ------------------------------------


def test_the_components_rules_reach_every_markup_module_a_page_holds() -> None:
    """A page's markup is markup, so the three rules `test_components.py` holds cover it too.

    The scope of those rules is asserted here rather than there: a page whose markup escapes
    them would leave that file green and this one red, which is the way round that says which
    file has to change.
    """
    covered = set(test_components.SOURCES)
    # The pages hold markup to cover...
    assert markup_modules(), "no page holds a markup module"
    # ...and every module of it is one the components rules are read over.
    assert set(markup_modules()) <= covered
