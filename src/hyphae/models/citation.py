"""One statement a read ran and what it bound: the fact a footer cites and a report re-runs.

A store read hands one back beside its rows and the page passes it on unread, so the page
never names a query. What a binding may be is declared here too: it crosses the store's line
inside every citation.
"""

import datetime as dt
from collections.abc import Mapping
from typing import NamedTuple

# What a bound parameter can be. NULL is a real default — `$since` unset means the whole
# corpus — so absence cannot stand in for "required" (`store/library.py:REQUIRED`).
ParamValue = str | int | dt.date | None


class Citation(NamedTuple):
    """One query a read ran, by the file stem the library loads it under, at the bindings it ran.

    The bindings keep the order they were bound in: the footer quotes them in that order, and
    the query page rebinds them from it.
    """

    name: str
    bindings: Mapping[str, ParamValue]
