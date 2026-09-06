"""What the errors page's read hands its markup: the failures, the cap, and the evidence.

Neutral by design (`plans/deepen-viewer-reads/design.md`): no request, no response, no element
and no raw store row. `held` is the one fact the page needs and does not print — a session the
store never held and one whose calls all succeeded are the same empty list and not the same
answer, so the read says which and the route words it.
"""

from collections.abc import Mapping, Sequence
from typing import NamedTuple

from hyphae.view.citation import Cited
from hyphae.view.failures import Failure


class ErrorsPage(NamedTuple):
    """One session's failed tool calls, in the order they happened."""

    session_id: str
    listed: Sequence[Failure]
    # How many the session failed beyond what the cap admits, for the tail that says so.
    cut: int
    # Whether the store holds the session at all, read only when there is a 404 to word.
    held: bool
    citations: Mapping[str, Cited]
