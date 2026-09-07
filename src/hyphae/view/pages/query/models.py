"""What the query page's read hands its markup: one statement, and how it was cited.

Neutral by design (`plans/deepen-viewer-reads/design.md`): no request, no response and no
element. `bindings` is the one place a request's own text reaches rendering, and it crosses
this seam as plain data rather than as the request.
"""

from collections.abc import Mapping
from typing import NamedTuple


class QueryPage(NamedTuple):
    """One library query as the page that cited it links to."""

    name: str
    sql: str
    # What a shell has to run first where the statement calls a library macro, empty where it
    # calls none.
    macro_setup: str
    # Whatever the citation carried, printed back rather than bound to anything: this page
    # runs no query, so a binding here is a fact about the page that sent you.
    bindings: Mapping[str, str]
