"""Reading one library query out of the build: the statement, and the setup it needs.

The one page read that opens no store — the query library is what this page reads. Nothing
above this module names the library or the loader.
"""

from collections.abc import Mapping

from hyphae.store import library, macros
from hyphae.view.pages.query.models import QueryPage


def query(name: str, bindings: Mapping[str, str]) -> QueryPage | None:
    """One library query's SQL, or None where no query of that name ships with this build.

    The name is a stem the library lists and never a path, which is what makes a request
    for `../../secret` a miss rather than a file (`docs/viewer.md`).
    """
    if name not in library.names():
        return None
    statement = library.load(name)
    return QueryPage(
        name=name,
        sql=statement,
        # What a shell has to run first, where the statement calls a library macro: both
        # consumers install these, and a reader pasting the statement alone has no way to find
        # out why the catalog does not know the name.
        macro_setup=macros.needed_by(statement),
        bindings=bindings,
    )
