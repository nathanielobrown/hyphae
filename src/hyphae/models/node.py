"""What a node's reads hand back across the store line, each with the statement that read it.

The four headers are one node read whole for its own page — one per kind that has fields
of its own; a bucket has none, and a compaction reads out of `view_compactions` — and
`WholeValue` is one fat value of a node, the rest of what its header cut. Each is built by
column name off the statement that answers it (`store/nodes.py`), under `row.ROW`, so a
column the statement gains or loses raises at the read and not on a reader's page. The
rows they are built from stay in the store.
"""

import datetime as dt
from typing import TypedDict

from pydantic import with_config
from pydantic.dataclasses import dataclass

from hyphae.models.citation import Citation
from hyphae.models.row import ROW

# The `tool_fields` struct: every member a cut string, but `todos`, a count
# (`store/macros.py`); what a tool call's title is composed out of (`view/text/tool_names.py`).
ToolFields = dict[str, str | int | None]


@with_config(ROW)
class FirstTool(TypedDict):
    """The first tool an api call asked for, as its title names it: a `view_call_header` struct."""

    name: str
    fields: ToolFields


@with_config(ROW)
class CalledTools(TypedDict):
    """What an api call asked for, thin: the `tools` struct of `view_call_header`.

    Both members NULL on a call that asked for nothing; `names` is every tool in order,
    cut to the header's item count."""

    first: FirstTool | None
    names: list[str] | None


@dataclass(frozen=True, config=ROW)
class TurnHeader:
    """One turn's page, whole: a `view_turn_header` row.

    Stands apart from `trace.Turn` rather than deriving from it: the statement renames the
    id and the index, leaves the thread unselected, NULLs the prompt of a slash turn, and
    adds what the page prints under it — the cut values' counts, and the turn's own totals.
    """

    turn_index: int
    turn_id: str
    # What was typed, cut to the detail width; None on a slash turn, whose prompt is the
    # command and whose `command_args` carries what followed it.
    prompt: str | None
    prompt_chars: int | None
    command_name: str | None
    command_args: str | None
    command_args_chars: int | None
    started_at: dt.datetime
    ended_at: dt.datetime
    replayed: bool
    api_calls: int
    tool_calls: int
    tool_errors: int
    cost_usd: float
    # How many of the turn's calls the price table left unpriced: the `*` the cost carries.
    unpriced_api_calls: int
    citation: Citation


@dataclass(frozen=True, config=ROW)
class RunHeader:
    """One agent run's page, whole: a `view_run_header` row."""

    run_id: str
    session_id: str
    agent_type: str
    brief: str | None
    brief_chars: int | None
    # The alias the run asked for, not the model that answered its calls.
    model: str | None
    # Read off the call that spawned the run; None where the store holds no such call, or
    # where the tool that spawned it was asked in other words.
    prompt: str | None
    prompt_chars: int | None
    result: str | None
    result_chars: int | None
    spawn_depth: int | None
    is_fork: bool
    parent_agent_id: str | None
    tool_use_id: str | None
    started_at: dt.datetime | None
    ended_at: dt.datetime | None
    wall_ms: int | None
    turns: int
    api_calls: int
    tool_calls: int
    tool_errors: int
    # How often the run's own thread compacted.
    compactions: int
    output_tokens: int
    cost_usd: float
    unpriced_api_calls: int
    citation: Citation


@dataclass(frozen=True, config=ROW)
class CallHeader:
    """One api call's page, whole: a `view_call_header` row."""

    call_index: int
    api_call_id: str
    # None on a call that answers no turn: one the unattributed bucket gathers.
    turn_id: str | None
    model: str
    fallback_from: str | None
    effort: str | None
    stop_reason: str | None
    attribution_skill: str | None
    started_at: dt.datetime
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    # None where the price table does not price the model, which `unpriced_api_calls` counts.
    cost_usd: float | None
    unpriced_api_calls: int
    text: str
    text_chars: int
    thinking: str
    thinking_chars: int
    tool_calls: int
    tools: CalledTools
    citation: Citation


@dataclass(frozen=True, config=ROW)
class ToolHeader:
    """One tool call's page, whole: a `view_tool_header` row."""

    tool_index: int
    tool_call_id: str
    session_id: str
    api_call_id: str
    turn_id: str | None
    name: str
    fields: ToolFields
    server_side: bool
    is_error: bool
    # No result reached the transcript: the session ended, or the call was refused, first.
    incomplete: bool
    offload_file: str | None
    # The agent run this call spawned, where it did.
    run_id: str | None
    started_at: dt.datetime
    ended_at: dt.datetime | None
    wall_ms: int | None
    input: str
    input_chars: int
    result: str | None
    result_chars: int | None
    # What a `Bash` call ran, which the input holds escaped onto one line; None elsewhere.
    command: str | None
    command_chars: int | None
    # The suffix of the file a `Read` returned, which decides how the result is marked up.
    result_type: str | None
    citation: Citation


# Any of the four, for the read they share.
NodeHeader = TurnHeader | RunHeader | CallHeader | ToolHeader


@dataclass(frozen=True, config=ROW)
class WholeValue:
    """One fat value of a node, whole: the rest of what a pane previewed at its width."""

    # None is a row the store holds with nothing under it — a `Read` has no command, a turn
    # no prompt — which the fetch that serves it turns into its 404.
    value: str | None
    citation: Citation
    # The suffix of the file a `Read` returned, which decides how the value is marked up
    # (`view/detail.py:syntax_of`). Only the named-file statement selects it; None elsewhere.
    result_type: str | None = None
