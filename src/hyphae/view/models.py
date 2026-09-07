"""What the shared components are handed — the page models more than one page's read builds.

The seam a page draws at `pages/*/models.py`, one layer down. A shape two pages build and one
shared component prints has no page to belong to, and leaving it beside the component would
make every model that carries it hold htpy: a page model is neutral, and a value it is made of
has to be too (`plans/deepen-viewer-reads/design.md`).

So `components/parts.py` says how these print and this says what they are.
"""

from typing import NamedTuple


class Count(NamedTuple):
    """One name a session's row counts, and how often it counted it.

    Built at the read from whichever column the query counted — runs for an agent type, turns
    for a kind of work — so the component prints a count without knowing what was counted.
    """

    name: str
    count: int


class Step(NamedTuple):
    """One side of a pager: where the link goes, and what it is called there.

    The words belong to the sequence rather than to the control: a children log steps to the
    previous page, and the session list — newest first — steps to a newer one.
    """

    href: str
    words: str


class Pager(NamedTuple):
    """Where a page sits in a sequence, and the way to either side of it.

    `field` names the words between the links for a reader looking for them: a log's `place`
    is which page of how many, the list's `range` which sessions of the store.
    """

    field: str
    words: str
    previous: Step | None
    next: Step | None
