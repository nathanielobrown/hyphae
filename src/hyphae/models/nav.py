"""What the NavTree's reads hand back across the store line: the rows its three levels and
the session's runs are built from.

A NavTree row is a node in outline — what to call it, what it cost, where it left the
window — cut to the NavTree's widths, so these stand apart from the children-log rows in
`models/node.py` that list the same nodes at a log's widths with a log's columns. Each is
built by column name off the statement that answers it (`store/nav.py`), under `row.ROW`.
"""

import datetime as dt
from typing import TypedDict

from pydantic import with_config
from pydantic.dataclasses import dataclass

from hyphae.models.listing import Context
from hyphae.models.node import CalledTools, ToolFields
from hyphae.models.row import ROW


@with_config(ROW)
class TurnContext(TypedDict):
    """Where a turn left the model's window: the `context` struct of `view_nav_tree_turns`.

    One member wider than `Context`: `base`, what the session opened on, which is the band
    a turn's bar runs dark from. NULL on a session the store holds no `main` call for.
    """

    # NULL on a turn of nothing but synthetic replies, which moved no window.
    fill: int | None
    added: int
    base: int | None
    window: int | None


@dataclass(frozen=True, config=ROW)
class NavTurnRow:
    """One turn as the NavTree lists a thread's: a `view_nav_tree_turns` row."""

    turn_index: int
    turn_id: str
    # What was typed, cut to the NavTree's width: the command on a slash turn.
    prompt: str
    command_name: str | None
    command_args: str | None
    started_at: dt.datetime
    cost_usd: float
    unpriced_api_calls: int
    context: TurnContext


@dataclass(frozen=True, config=ROW)
class NavCallRow:
    """One api call as the NavTree lists a turn's — or a thread's unattributed bucket's: a
    `view_nav_tree_calls` row."""

    call_index: int
    api_call_id: str
    # What the call said, cut to the NavTree's width.
    text: str
    model: str
    tools: CalledTools
    # None on a synthetic reply, which reports no tokens and so says nothing about the window.
    context: Context | None
    started_at: dt.datetime
    # None where the price table does not price the model, which `unpriced_api_calls` counts.
    cost_usd: float | None
    unpriced_api_calls: int


@dataclass(frozen=True, config=ROW)
class NavToolRow:
    """One tool call as the NavTree lists an api call's — or, with no api call named, every
    one under a turn: a `view_nav_tree_tools` row."""

    call_index: int
    tool_index: int
    tool_call_id: str
    name: str
    fields: ToolFields
    started_at: dt.datetime
    is_error: bool
    # What the api call holding this tool call cost — the one surface that spends it. None
    # where the price table does not price the model, which `unpriced_api_calls` counts.
    call_cost_usd: float | None
    unpriced_api_calls: int


@dataclass(frozen=True, config=ROW)
class RunRow:
    """One agent run of a session, with where it hangs: a `view_runs` row.

    The three `spawn_*` members are one join: the call that spawned the run, its thread and
    its turn. All three NULL is an unattached run, the session's one bucket of them.
    """

    run_id: str
    agent_type: str
    brief: str | None
    model: str | None
    spawn_depth: int
    is_fork: bool
    parent_agent_id: str | None
    tool_use_id: str | None
    started_at: dt.datetime
    ended_at: dt.datetime
    cost_usd: float
    unpriced_api_calls: int
    tool_errors: int
    compactions: int
    # A struct of nulls on a run whose thread made no call: a bar the NavTree does not draw.
    context: Context
    spawn_source: str | None
    spawn_turn_id: str | None
    spawn_call_id: str | None
