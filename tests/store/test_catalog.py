"""The catalog and the store package name the same viewer statements.

A `view_*` statement is reached only by name, and the name is a string constant in the store
package: an enum member's value today, a repository method's argument as phase 4 lands. Read
off the source, because a statement no module names ships and runs nowhere, and a name no
statement backs fails only when the module that spells it is called — so both are held here
rather than at the call. Every `view_` literal in `src/hyphae/store/**/*.py` is the set pinned,
`==` the catalog's `view_` names.
"""

import ast
import re
from pathlib import Path

import pytest

import hyphae.store
from hyphae.store import library
from hyphae.store.library import VIEW_PREFIX

STORE = Path(hyphae.store.__file__).parent
# A whole statement name: the prefix alone (`VIEW_PREFIX` itself is a constant in this package)
# does not match, nor does a `view_` inside SQL text or a docstring.
STATEMENT = re.compile(rf"{VIEW_PREFIX}[a-z_]+")
# The two timelines the viewer shares with `hp query`: the only statements a page binds that
# ship under no `view_` prefix, so a scan over the viewer's statements adds them by name.
TIMELINES = frozenset({"session_timeline", "run_timeline"})


def viewer_statements() -> set[str]:
    """Every statement the viewer reads: the catalog's `view_` names, plus the two timelines."""
    return {name for name in library.names() if name.startswith(VIEW_PREFIX)} | TIMELINES


def named_in_store() -> set[str]:
    """Every string constant in the store package that spells a whole viewer statement name."""
    return {
        node.value
        for path in sorted(STORE.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path)))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and STATEMENT.fullmatch(node.value)
    }


@pytest.mark.reads_the_repo  # reads the store package's source
def test_every_view_statement_is_named_in_the_store_package_and_nothing_else() -> None:
    shipped = {name for name in library.names() if name.startswith(VIEW_PREFIX)}
    assert named_in_store() == shipped
