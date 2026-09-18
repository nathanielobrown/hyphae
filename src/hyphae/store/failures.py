"""The errors page's read: every failed tool call of one session, whichever thread it ran on.

`FailureRepository` is the seam: the errors page and the error stepper call `failures` with
the session's id and the width a row names its node at, and read `Failure` models back in
the order the calls happened, with the count the cap left off and the citation the footer
quotes.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from hyphae.models.citation import Citation
from hyphae.models.failure import Failure, Failures
from hyphae.store import library

if TYPE_CHECKING:
    # The handle hands out this repository, and this repository holds the handle: the one cycle
    # the design has, so the name is the checker's only.
    from hyphae.store.handle import Store

# Why the list is session-wide and capped rather than paged is the statement's own header.
SESSION_ERRORS = "view_session_errors"


class FailureRepository:
    """The errors page's read, over one open store: `store.failures`.

    Keyword-only, one keyword per key the statement binds, with the surface's widths as one
    mapping (`bounds.ERRORS_WIDTHS._asdict()`); `library.bind` fills what the statement
    declares and refuses the rest. A plain class rather than a dataclass: mutmut skips every
    decorated class, and the handle builds one of these per store anyway.
    """

    def __init__(self, store: "Store") -> None:
        self.store = store

    def failures(self, *, session_id: str, widths: Mapping[str, int]) -> Failures:
        """Every failed tool call of one session in the order they happened, up to the cap.

        A session the store never held and one whose calls all succeeded are the same answer
        here — no rows, nothing cut — and the page tells them apart by reading the header.
        """
        bindings = library.bind(SESSION_ERRORS, widths, {}, session_id=session_id)
        rows = [
            Failure(**row)
            for row in library.fetch(self.store, library.load(SESSION_ERRORS), bindings)
        ]
        return Failures(rows, library.dropped(rows), Citation(SESSION_ERRORS, bindings))
