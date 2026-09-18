"""Reading one chunk of an offloaded tool result out of the store, at the offset a URL carried.

The whole document from one open of the store, closed before anything renders
(`view/deps.py`, the window trade-off). Nothing above this module names a query, a binding or
a store column.
"""

from pathlib import Path

from hyphae.store.handle import open_store
from hyphae.store.trace_store import PAGE_WAIT
from hyphae.view.citation import cited
from hyphae.view.pages.offload.models import OffloadFile, OffloadPage


def offload(db: Path, session_id: str, name: str, after: int, size: int) -> OffloadPage | None:
    """One chunk of a tool result, or None where the session offloaded no file of that name.

    The name is a key into the store and never a path the server opens, which is what makes
    the shape of it uninteresting.
    """
    with open_store(db, read_only=True, wait=PAGE_WAIT) as store:
        chunk = store.offloads.chunk(session_id=session_id, name=name, after=after, size=size)
    if chunk is None:
        return None
    file = OffloadFile(
        name=chunk.name,
        size_bytes=chunk.size_bytes,
        content_chars=chunk.content_chars,
        lossy_decode=chunk.lossy_decode,
        chunk=chunk.chunk,
    )
    served = after + len(file.chunk)
    return OffloadPage(
        session_id=session_id,
        file=file,
        after=served if served < file.content_chars else None,
        size=size,
        citations={chunk.citation.name: cited(chunk.citation)},
    )
