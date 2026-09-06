"""What the landing page's read hands its markup: the rows, the windows, and the evidence.

Neutral by design (`plans/deepen-viewer-reads/design.md`): a value that crosses this seam
knows nothing about requests, responses, elements, or the raw columns it came out of. The
citations ride along because the evidence for a page is part of what reading it produced.
"""

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from hyphae.view.citation import Cited


class ProjectRow(NamedTuple):
    """One project as the landing page prints it: three windows of spend, and when it last ran.

    `link` is the session list narrowed to this project, or None where there is no list to
    open — a session that named no directory, or a path longer than the head the page shows.
    A window the project has no sessions in sums nothing, so its cost and its unpriced count
    are absent rather than zero.
    """

    project_dir: str | None
    link: str | None
    recent_sessions: int
    recent_cost: float | None
    recent_unpriced: int | None
    window_sessions: int
    window_cost: float | None
    window_unpriced: int | None
    sessions: int
    cost_usd: float
    unpriced_api_calls: int
    last_active: dt.datetime | None


class ProjectsPage(NamedTuple):
    """Everything one read of the landing page found, in the shape the page prints it."""

    rows: Sequence[ProjectRow]
    """Every project the store holds sessions for, most recently active first."""

    recent_days: int
    """The shorter trailing window, as the query bound it — what its column is headed with."""

    window_days: int
    """The longer trailing window, likewise: a heading cannot say one thing while its column
    counts another when both read the binding."""

    cut: int
    """The projects the query counted before its LIMIT and the page does not show."""

    citations: Mapping[str, Cited]
    """The queries this read ran, bound as it ran them."""
