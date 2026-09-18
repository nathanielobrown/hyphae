"""What the session list, the landing page and a session's header read: one model per row.

Each is built by column name off the statement that answers it (`store/sessions.py`), under
`row.ROW`, so a column the statement gains or loses raises at the read. The containers under
them carry what a page prints beside the rows: whether a page follows, what a limit cut, and
the citation a footer quotes.
"""

import datetime as dt
from typing import NamedTuple, TypedDict

from pydantic import with_config
from pydantic.dataclasses import dataclass

from hyphae.models.citation import Citation
from hyphae.models.row import ROW


@with_config(ROW)
class AgentTypeCount(TypedDict):
    """One kind of agent a session ran, and how many runs of it: a `view_sessions` struct."""

    name: str
    runs: int


@with_config(ROW)
class WorkCount(TypedDict):
    """One category a pass gave the session's turns, and how many: a struct of
    `view_described_sessions`."""

    name: str
    turns: int


@with_config(ROW)
class Context(TypedDict):
    """Where a thread stood in the model's window: the `context` struct of `view_session_header`,
    and of `view_compactions`, whose rows carry where the thread stood when it compacted."""

    fill: int | None
    # What a turn grew the window by, which a session has no one answer for: NULL on a session.
    added: int | None
    window: int | None


@dataclass(frozen=True, config=ROW)
class SessionFigures:
    """What every surface printing a session carries: its identity, counts, tokens, cost,
    durations and skills. The list row and the header each add what its own surface prints."""

    session_id: str
    started_at: dt.datetime | None
    title: str | None
    project_dir: str | None
    turns: int
    api_calls: int
    tool_calls: int
    agent_runs: int
    compactions: int
    cost_usd: float
    unpriced_api_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    wall_ms: int | None
    active_ms: int | None
    tool_errors: int
    # Names, never content: which skills ran, cut to the row's head, and how many were left off.
    skills: list[str]
    skills_cut: int


@dataclass(frozen=True, config=ROW)
class SessionRollup(SessionFigures):
    """One row of the session list, cut to the list's widths."""

    # Busiest first; the count the row could not print is beside it.
    agent_types: list[AgentTypeCount]
    agent_types_cut: int


@dataclass(frozen=True, config=ROW)
class SessionDescription:
    """What a pass said one session was, beside the kinds of work its turns were.

    Either half stands on its own: a pass that reached a session's turns but not the session
    leaves the three strings NULL, and one the list joins to no row at all leaves every column
    NULL — so the join's half is nullable throughout.
    """

    session_id: str
    description: str | None
    category: str | None
    outcome: str | None
    work: list[WorkCount] | None
    work_cut: int | None


@dataclass(frozen=True, config=ROW)
class DescribedSessionRollup(SessionDescription, SessionRollup):
    """A list row joined to what a pass said about it: both halves, no column of its own."""


@dataclass(frozen=True, config=ROW)
class Project:
    """One project the filter box suggests, and how many sessions it holds."""

    project_dir: str
    sessions: int


@dataclass(frozen=True, config=ROW)
class ProjectRollup:
    """One row of the landing page: a project's whole history and two trailing windows."""

    project_dir: str | None
    # What the list's `?project=` filter matches: the whole path, where `project_dir` is cut.
    project_filter: str | None
    recent_sessions: int
    # NULL when the window holds no session: nothing to sum.
    recent_cost: float | None
    recent_unpriced: int | None
    window_sessions: int
    window_cost: float | None
    window_unpriced: int | None
    sessions: int
    cost_usd: float
    unpriced_api_calls: int
    last_active: dt.datetime | None
    # How many rows the statement matched before its limit, on every row alike.
    matched_rows: int


@dataclass(frozen=True, config=ROW)
class SessionHeader(SessionFigures):
    """One session's header, cut to the pane's widths, with the statement that read it."""

    # What the list's `?project=` filter matches: the whole path, where `project_dir` is cut.
    project_filter: str | None
    git_branch: str | None
    version: str | None
    entrypoint: str | None
    ended_at: dt.datetime | None
    pr_urls: list[str]
    pr_urls_cut: int
    context: Context
    citation: Citation


class Listing(NamedTuple):
    """One page of the session list, and whether a page follows it."""

    rows: list[SessionRollup]
    more: bool
    # The composed statement at its window, then the joined one where the store had a pass to join.
    ran: list[Citation]


class ProjectRollups(NamedTuple):
    """The landing page's rows, and how many projects its limit left off."""

    rows: list[ProjectRollup]
    cut: int
    citation: Citation


class Answer[T](NamedTuple):
    """Every row a statement answered, with the citation for it."""

    rows: list[T]
    citation: Citation


class Listed[T](NamedTuple):
    """One numbered page of a level: the rows, how many the level holds in all, and the citation.

    `total` is the count before the LIMIT bit, which is what lets a page say which of how many
    it is — and what lets a heading count the level rather than the rows in front of the reader.
    """

    rows: list[T]
    total: int
    citation: Citation
