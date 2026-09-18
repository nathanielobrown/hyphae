"""The offload page's read: one chunk of a tool result Claude Code wrote to a file.

`OffloadRepository` is the seam: the page calls `chunk` with the file's keys and the window a
URL carried, and reads an `Offload` model back with the citation its footer quotes. The name
is the transcript's own file name — a key into the store here and nothing else; nothing in
this package opens a path.
"""

from typing import TYPE_CHECKING

from hyphae.models.citation import Citation
from hyphae.models.record import Offload
from hyphae.store import library

if TYPE_CHECKING:
    # The handle hands out this repository, and this repository holds the handle: the one cycle
    # the design has, so the name is the checker's only.
    from hyphae.store.handle import Store

# One chunk of an offloaded tool result, cut in characters: the content has no ceiling, so it
# is read a window at a time.
OFFLOAD = "view_offload"


class OffloadRepository:
    """The offload page's read, over one open store: `store.offloads`.

    Keyword-only, one keyword per key the statement binds; it prints at no width, so there
    is none to pass. `library.bind` still holds the call to the statement. A plain class
    rather than a dataclass: mutmut skips every decorated class, and the handle builds one of
    these per store anyway.
    """

    def __init__(self, store: "Store") -> None:
        self.store = store

    def chunk(self, *, session_id: str, name: str, after: int, size: int) -> Offload | None:
        """`size` characters of one offloaded file from `after`, or None where the session
        offloaded no file of that name.

        Past the end of a file the session did offload, the row is still the file's: an empty
        chunk, which the page reads as "no next chunk" — never None.
        """
        bindings = library.bind(
            OFFLOAD, {}, {}, session_id=session_id, name=name, after_chars=after, chunk_chars=size
        )
        row = library.one(self.store, OFFLOAD, bindings)
        return None if row is None else Offload(citation=Citation(OFFLOAD, bindings), **row)
