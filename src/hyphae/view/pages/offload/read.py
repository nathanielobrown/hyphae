"""Reading one chunk of an offloaded tool result out of the store, at the offset a URL carried.

The whole document from one open of the store, closed before anything renders
(`view/deps.py`, the window trade-off). Nothing above this module names a query, a binding or
a store column.
"""

from pathlib import Path

from hyphae.analyze.queries import ParamValue
from hyphae.view.citation import cited
from hyphae.view.pages.offload.models import OffloadFile, OffloadPage
from hyphae.view.store import Page, open_store, page_rows


def offload(db: Path, session_id: str, name: str, after: int, size: int) -> OffloadPage | None:
    """One chunk of a tool result, or None where the session offloaded no file of that name.

    The name is a key into the store and never a path the server opens, which is what makes
    the shape of it uninteresting.
    """
    binds: dict[str, ParamValue] = {
        "session_id": session_id,
        "name": name,
        "after_chars": after,
        "chunk_chars": size,
    }
    with open_store(db) as connection:
        rows = page_rows(connection, Page.OFFLOAD, **binds)
    if not rows:
        return None
    row = rows[0]
    file = OffloadFile(
        name=row["name"],
        size_bytes=row["size_bytes"],
        content_chars=row["content_chars"],
        lossy_decode=row["lossy_decode"],
        chunk=row["chunk"],
    )
    served = after + len(file.chunk)
    return OffloadPage(
        session_id=session_id,
        file=file,
        after=served if served < file.content_chars else None,
        size=size,
        citations={Page.OFFLOAD.value: cited(Page.OFFLOAD, binds)},
    )
