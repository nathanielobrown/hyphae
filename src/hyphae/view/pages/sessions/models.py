"""What one request asked of the session list, and what reading it answered with.

Neutral by design (`plans/deepen-viewer-reads/design.md`): the values here name no request, no
response, no element and no raw store row. `ListParams` is the ask a URL parsed to, which the
read binds and the links the page mints reproduce; `SessionsPage` is what came back.
"""

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from hyphae.analyze.queries import ParamValue
from hyphae.view.citation import Cited
from hyphae.view.models import Count


class ListParams(NamedTuple):
    """What a request asked the list for, each value already checked against its closed set.

    `filters` is what the query binds and `given` is what the URL said, kept as text because
    the form comes back holding it and every link the page mints carries it. A filter left
    blank is in `given` and not in `filters`: the form submits every field.
    """

    sort: str
    direction: str
    page: int
    size: int
    filters: Mapping[str, ParamValue]
    given: Mapping[str, str]


class Described(NamedTuple):
    """What a pass said one session was, as a row of the list prints it.

    Three values or none of them: a row the pass reached carries all three, and a row it has
    not carries no enrichment line at all.
    """

    description: str
    category: str
    outcome: str


class SessionRow(NamedTuple):
    """One session as a row of the list prints it, built from its store row.

    The three lists grow with a session, so the query cuts each and says how many it left: a
    row of the list is multiplied by the size of the page. `description` and the two tags come
    from an enrichment pass and are absent over a store no pass has reached.
    """

    session_id: str
    started_at: dt.datetime | None
    title: str | None
    project_dir: str | None
    turns: int
    api_calls: int
    tool_calls: int
    compactions: int
    tool_errors: int
    cost_usd: float
    output_tokens: int
    unpriced_api_calls: int
    wall_ms: int | None
    active_ms: int | None
    agent_types: Sequence[Count]
    agent_types_cut: int
    skills: Sequence[str]
    skills_cut: int
    work: Sequence[Count]
    work_cut: int
    described: Described | None


class SessionsPage(NamedTuple):
    """One page of the list, and everything the store had to be open to say.

    `describes` decides both what the query joined and what the page cites, so it crosses the
    seam beside the rows it changed. `more` is the row the query read past the page: the list
    has no last page to number against, only a next one or none.
    """

    rows: Sequence[SessionRow]
    projects: Sequence[str]
    describes: bool
    more: bool
    citations: Mapping[str, Cited]
