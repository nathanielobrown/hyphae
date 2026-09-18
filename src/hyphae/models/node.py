"""What a node's reads hand back across the store line, each with the statement that read it.

The four headers are one node read whole for its own page — one per kind that has fields
of its own; a bucket has none, and a compaction reads out of `view_compactions` — and
`WholeValue` is one fat value of a node, the rest of what its header cut. Under them are the
rows a children log lists a page of, the bucket its timeline lists beside them, a thread's
compactions, the numbers a NavTree row's popover prints, and the join from a turn to the
transcript line it was read from. Each is built by column name off the statement that answers
it (`store/nodes.py`), under `row.ROW`, so a column the statement gains or loses raises at the
read and not on a reader's page. The rows they are built from stay in the store.
"""

import datetime as dt
from typing import TypedDict

from pydantic import with_config
from pydantic.dataclasses import dataclass

from hyphae.models.citation import Citation
from hyphae.models.listing import Context
from hyphae.models.row import ROW

# The `tool_fields` struct: every member a cut string, but `todos`, a count
# (`store/macros.py`); what a tool call's title is composed out of (`view/text/tool_names.py`).
ToolFields = dict[str, str | int | None]


@with_config(ROW)
class NamedTool(TypedDict):
    """One tool call as its title names it: the `{name, fields}` struct every statement that
    lists tool calls beside a node answers, whether one, a call's own, or a tool's siblings."""

    name: str
    fields: ToolFields


@with_config(ROW)
class CalledTools(TypedDict):
    """What an api call asked for, thin: the `tools` struct of `view_call_header`.

    Both members NULL on a call that asked for nothing; `names` is every tool in order,
    cut to the header's item count."""

    first: NamedTool | None
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


# --- the children logs ------------------------------------------------------------------------


@dataclass(frozen=True, config=ROW)
class CallRow:
    """One api call as the log under a turn — or a thread's unattributed bucket — lists it: a
    `view_turn_calls` row."""

    call_index: int
    api_call_id: str
    model: str
    fallback_from: str | None
    # What the call said, cut to the log's width; the count is its whole length.
    text: str
    text_chars: int
    thinking_chars: int
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
    tool_calls: int
    # Every tool the call asked for, in order, for the log row to name; None where it asked
    # for nothing.
    called_tools: list[NamedTool] | None
    # How many calls the level holds before the page's LIMIT bit, on every row alike.
    matched_rows: int


@dataclass(frozen=True, config=ROW)
class ToolRow:
    """One tool call as the log under an api call lists it: a `view_call_tools` row."""

    tool_index: int
    tool_call_id: str
    name: str
    fields: ToolFields
    server_side: bool
    is_error: bool
    # No result reached the transcript: the session ended, or the call was refused, first.
    incomplete: bool
    offload_file: str | None
    started_at: dt.datetime
    input_chars: int
    result_chars: int | None
    matched_rows: int


@dataclass(frozen=True, config=ROW)
class TimelineRow:
    """One turn as a thread's timeline lists it: a `session_timeline` or `run_timeline` row,
    paged through `store/paging.py:window`, which is what adds the count."""

    turn_index: int
    turn_id: str
    # What was typed, cut to the log's width: the command on a slash turn.
    prompt: str
    command_name: str | None
    command_args: str | None
    started_at: dt.datetime
    api_calls: int
    tool_calls: int
    tool_errors: int
    cost_usd: float
    unpriced_api_calls: int
    matched_rows: int


@dataclass(frozen=True, config=ROW)
class UnattributedRow:
    """A thread's bucket of api calls that answer no turn, as its timeline lists it: the one
    `session_timeline` or `run_timeline` row with no turn index, read without a page around it
    (`store/paging.py:cursorless_rows`). Every turn column but the id and the counts is NULL."""

    turn_index: None
    turn_id: str
    prompt: None
    command_name: None
    command_args: None
    started_at: dt.datetime
    api_calls: int
    tool_calls: int
    tool_errors: int
    cost_usd: float
    unpriced_api_calls: int


@dataclass(frozen=True, config=ROW)
class CompactionRow:
    """One compaction as its thread's set lists it: a `view_compactions` row."""

    compaction_id: str
    timestamp: dt.datetime
    # The turn it happened during; None where it fell between two.
    turn_id: str | None
    trigger: str
    pre_tokens: int
    post_tokens: int
    duration_ms: int
    context: Context


# --- the popovers -----------------------------------------------------------------------------


@with_config(ROW)
class SpentGroup(TypedDict):
    """One model's summed tokens under a node: a member of `view_numbers`'s `spent` list, which
    the page prices at that model's rates (`pricing.py:TokenUsage` takes the same six)."""

    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    # The cache-creation total split by TTL, summed under the fallback the price table applies
    # to one call: a call that reported no split puts its whole write on the 5-minute rate.
    cache_5m_tokens: int
    cache_1h_tokens: int


@dataclass(frozen=True, config=ROW)
class NodeNumbers:
    """The numbers behind one NavTree row of a node made of api calls: the `view_numbers` row.

    The counts are the node's last answering call and come to the window above them; the
    dollars are every call it made. Every column but `subtree_usd` and the two counts is None
    on a node with no api calls under it, which the popover prints as the dashes it is.
    """

    model: str | None
    window_tokens: int | None
    cache_read_tokens: int | None
    new_input_tokens: int | None
    output_tokens: int | None
    fill: int | None
    # What the node grew the window by, which a session has no one answer for: None there.
    added: int | None
    cost_usd: float | None
    # What the agent runs under the node cost; zero where none hang under it.
    subtree_usd: float
    session_usd: float | None
    unpriced_api_calls: int
    api_calls: int
    spent: list[SpentGroup]
    citation: Citation


@dataclass(frozen=True, config=ROW)
class ToolNumbers:
    """The numbers behind one NavTree row of a tool call: the `view_numbers_tool` row."""

    input_chars: int
    result_chars: int | None
    offload_file: str | None
    # The first few of the calls asked beside this one, and how many the head left off.
    siblings: list[NamedTool]
    siblings_cut: int
    spawned_run: bool
    citation: Citation


@dataclass(frozen=True, config=ROW)
class CompactionNumbers:
    """The numbers behind one NavTree row of a compaction: the `view_numbers_compaction` row."""

    pre_tokens: int
    post_tokens: int
    freed: int
    trigger: str
    citation: Citation


# --- the record behind a turn -----------------------------------------------------------------


@dataclass(frozen=True, config=ROW)
class TurnRecord:
    """Which transcript line one turn was read from: a `view_turn_records` row."""

    turn_id: str
    line_no: int
