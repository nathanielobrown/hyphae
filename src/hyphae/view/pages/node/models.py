"""What a node page's read hands its markup: the node, where it sits, and what hangs under it.

Neutral by design (`plans/deepen-viewer-reads/design.md`): no request, no response, no element
and no raw store row. Every shape both sides of the seam name is declared here and nowhere
else, down to the row types the four groups are made of — a read that reached into the markup
for a row would put an element's own module on the store's side of the wall, and markup that
declared one would make the read import it back.

Read top to bottom it goes small to large: what one store row is read into, then the groups a
page gathers those into, then the four answers a route returns.
"""

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from hyphae.view.citation import Cited
from hyphae.view.detail import Detail, EnrichmentLines
from hyphae.view.enrichment import Enrichment
from hyphae.view.failures import Step as Failures
from hyphae.view.models import Pager
from hyphae.view.nodes import Node, Preset
from hyphae.view.pages.node.columns import Shape
from hyphae.view.text import highlight

# --- What one store row is read into (`pages/node/reads.py`) -------------------------------


class SessionFacts(NamedTuple):
    """The session everything else was recorded in: where it ran, and what it came to.

    Neither the name it was recorded under nor the directory it ran in is here: the heading
    above prints the one and the crumb above that links the other, and a fact is for what
    nothing else on the page says.
    """

    session_id: str
    git_branch: str | None
    version: str | None
    entrypoint: str | None
    started_at: dt.datetime | None
    wall_ms: int | None
    active_ms: int | None
    turns: int
    api_calls: int
    tool_calls: int
    tool_errors: int
    agent_runs: int
    compactions: int
    cost_usd: float | None
    unpriced_api_calls: int
    output_tokens: int
    # The one list among the facts, and the pull requests the session's commands touched. Each
    # grows with the session, so the query cuts it and says how many it left: a pane is the one
    # part of a page no size a reader types bounds.
    skills: Sequence[str]
    skills_cut: int
    pr_urls: Sequence[str]
    pr_urls_cut: int


class TurnFacts(NamedTuple):
    """One turn: what it was asked, when, and what answering it took.

    `command_name` is set where the turn was typed as a slash command — its prompt is the
    `<command-…>` wrapper Claude Code expanded it into, and what a reader is looking for is the
    command.
    """

    turn_id: str
    command_name: str | None
    turn_index: int
    started_at: dt.datetime | None
    replayed: bool
    api_calls: int
    tool_calls: int
    tool_errors: int
    cost_usd: float | None
    unpriced_api_calls: int


class RunFacts(NamedTuple):
    """One agent run: the definition it ran, where it was spawned, and what its thread came to."""

    run_id: str
    agent_type: str | None
    model: str | None
    spawn_depth: int
    is_fork: bool
    started_at: dt.datetime | None
    wall_ms: int | None
    turns: int
    api_calls: int
    tool_calls: int
    tool_errors: int
    compactions: int
    cost_usd: float | None
    unpriced_api_calls: int
    output_tokens: int


class CallFacts(NamedTuple):
    """One api call: the request that was made, and what came back."""

    call_index: int
    model: str | None
    fallback_from: str | None
    effort: str | None
    stop_reason: str | None
    attribution_skill: str | None
    started_at: dt.datetime | None
    tool_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cost_usd: float | None
    unpriced_api_calls: int


class ToolFacts(NamedTuple):
    """One tool call. No cost of its own: what it took is the api call's.

    `run_id` is set on a `Task` call, which is where an agent run begins; `offload_file` where
    the result was too large for the transcript and Claude Code wrote it beside one.
    """

    session_id: str
    run_id: str | None
    tool_index: int
    name: str | None
    server_side: bool
    is_error: bool
    incomplete: bool
    started_at: dt.datetime | None
    wall_ms: int | None
    offload_file: str | None


class CompactionFacts(NamedTuple):
    """One compaction: where the thread's context was rewritten, and what it cost in tokens."""

    trigger: str | None
    timestamp: dt.datetime | None
    pre_tokens: int | None
    post_tokens: int | None
    duration_ms: int | None


class BucketFacts(NamedTuple):
    """A bucket, which is not a row of the store.

    It stands for what attached to nothing, so it has a spend and a count and no fields of its
    own — both of them read off the node rather than off a query.
    """

    cost_usd: float | None
    unpriced_api_calls: int


# What a body may be handed. Total over the kinds a URL can name — a kind with no member would
# render a heading and nothing under it, which reads as a node with no facts.
type Facts = (
    SessionFacts | TurnFacts | RunFacts | CallFacts | ToolFacts | CompactionFacts | BucketFacts
)


class LoggedTurn(NamedTuple):
    """One turn as its parent's log prints it."""

    node: Node
    turn_index: int
    api_calls: int
    tool_calls: int
    started_at: dt.datetime | None


class LoggedCall(NamedTuple):
    """One api call as its turn's log prints it.

    `called` is the tools it went on to call, named the way their own rows name them: composed
    at the route from the rows the query shipped, because naming a tool call is Python's
    (`view/text/tool_names.py`).
    """

    node: Node
    call_index: int
    model: str | None
    text: str | None
    tool_calls: int
    called: str
    text_chars: int
    started_at: dt.datetime | None


class LoggedTool(NamedTuple):
    """One tool call as its call's log prints it.

    `about` is what the call was for where its title already says what it did — the second line
    under the wide column, empty for every tool whose title stands alone.
    """

    node: Node
    tool_index: int
    name: str | None
    about: str
    is_error: bool
    result_chars: int | None
    started_at: dt.datetime | None


class LoggedRun(NamedTuple):
    """One agent run as its parent's log prints it."""

    node: Node
    agent_type: str | None
    tool_errors: int
    started_at: dt.datetime | None


# What a log row may be. The union is total over the four shapes a log has columns for, so the
# dispatch that prints one has an arm per shape and a fifth kind of row is a type error at the
# call site (`pages/node/markup/logs.py`).
type Logged = LoggedTurn | LoggedCall | LoggedTool | LoggedRun


@dataclass(frozen=True)
class NavTreeRow:
    """One line of the NavTree: a node at its depth, or the tail standing for what a cap cut."""

    node: Node
    depth: int
    selected: bool
    # Whether this row is a step of the open path above the selection: the stylesheet clamps
    # those at the top of the scroller, so a reader deep in a level sees what they are inside.
    ancestor: bool
    # On a tail row, how many of `node`'s children the cap left out. Zero on a node's own row,
    # which is what tells the two apart.
    cut: int = 0
    # On a tail row, the key of the child the open path descends through, when this level holds
    # one. The row's own fetch carries it: the cap keeps that child whatever its place in the
    # level, so the fetch has to know it to leave it out of what it sends back.
    opened: str | None = None


class PresetChoice(NamedTuple):
    """One preset as the control above the NavTree offers it: where it goes, and whether we are
    in it."""

    preset: Preset
    url: str
    current: bool


class Window(NamedTuple):
    """A node measured in api calls: where it left the context window, and what it cost."""

    model: str | None
    fill: int | None
    window_tokens: int | None
    added: int | None
    cost_usd: float | None
    api_calls: int | None
    unpriced_api_calls: int | None


class Charge(NamedTuple):
    """One line of the charges column: a count of tokens, and what those tokens cost."""

    # What the popover calls the line, and the fields its two numbers are labelled with.
    label: str
    field: str
    cost_field: str
    tokens: int | None
    # None where our price table holds no rate for the model the node answered on. The count
    # beside it still prints: a reading we have no price for is not a reading we do not have.
    cost: float | None
    # The step class the dollar's ground is drawn at — the badge's own, so the popover and the
    # row it opened from wash one number the same way.
    wash: str


class Breakout(NamedTuple):
    """The two lines under the total, on a node with agent runs hanging below it.

    What the node's own thread spent is the column above; this is what the runs it asked for
    spent, and the two together. Absent where no run hangs there — see `numbers.breakout`.
    """

    # What the runs below the node spent, and what that is with the node's own added back.
    subagents: float
    total: float
    # The ground each is drawn on, the badge's own, as every other dollar here takes it.
    subagents_wash: str
    total_wash: str


class Tool(NamedTuple):
    """A tool call measured in characters: what it was passed, and what it gave back."""

    input_chars: int | None
    result_chars: int | None
    offload_file: str | None
    spawned_run: bool
    siblings: Sequence[str]
    siblings_cut: int


class Compaction(NamedTuple):
    """A compaction measured in the window it dropped: both ends, and the word recorded for why."""

    pre_tokens: int | None
    post_tokens: int | None
    freed: int | None
    trigger: str | None


class Whole(NamedTuple):
    """One fat value fetched on its own: what it says, what it is filed under, and its query.

    `detail` is the name the pane filed the value under, and nothing for a value that is
    nobody's detail — the archived record. The styling that tells an ask from an answer reads
    it, which is why the fragment carries it back out.
    """

    value: str | None
    detail: str | None
    citation: str


class Record(NamedTuple):
    """One raw transcript record, whole: its own header line, and the JSON under it."""

    line_no: int
    type: str
    uuid: str | None
    timestamp: dt.datetime | None
    raw_chars: int | None
    raw: str
    citation: str


class Walked(NamedTuple):
    """Where one control goes, and whether taking it leaves the level the reader is on."""

    node: Node
    # True where the step lands at an ancestor's level rather than beside the selection, which
    # is what the control marks: the reader is coming out of the branch they were reading.
    climbed: bool


# --- What a page gathers those into --------------------------------------------------------


class Trail(NamedTuple):
    """The way out of the session, above the nodes inside it.

    Neither step is a node, so neither carries a node's marks or a knob suffix — a click on
    either leaves the session. `project_url` is nothing where the store holds no path to filter
    the list by, and the project then prints without a link.
    """

    list_url: str
    project_dir: str | None
    project_url: str | None


class Said(NamedTuple):
    """What a pass wrote about the node, and the way to the whole of each line it wrote.

    One value rather than two: a pane that had the words without the links, or the links
    without the words, is not a state `view/detail.py` can produce.
    """

    enrichment: Enrichment
    lines: EnrichmentLines


class Archived(NamedTuple):
    """The bytes behind the node: the thread's transcript, and the line it was read from."""

    thread_url: str
    line_no: int | None


class Nav(NamedTuple):
    """The NavTree side: the preset control, the one open path, and the thread it was read for.

    Not `nav_tree.NavTree`, which is what building the tree produced: this is the half of it a
    page draws, and the preset control and the thread are the page's own.
    """

    choices: Sequence[PresetChoice]
    rows: Sequence[NavTreeRow]
    thread: str


class Body(NamedTuple):
    """The node read whole: its own fields, what a pass said about it, its fat values, its bytes.

    What the pane would still show if the session around it were gone — everything else the
    page carries is about where the node sits.
    """

    facts: Facts
    said: Said | None
    details: Sequence[Detail]
    archived: Archived


class Steps(NamedTuple):
    """Where reading in order goes: the node before this one on its level, and the one after."""

    previous: Walked | None
    next: Walked | None


class Bearings(NamedTuple):
    """Where the node sits, and every way off it that is not a step down into a child.

    Three ways out, and going down is the NavTree's: back out of the session along the crumb
    chain, along the level with the walk, and across to another failure with the stepper.
    """

    trail: Trail
    chain: Sequence[Node]
    walked: Steps
    # How many tool calls the session failed, which is what the way into the errors page says.
    tool_errors: int | None
    # The failures either side of this node, where the pane is standing on one.
    failures: Failures | None


class Children(NamedTuple):
    """One page of the node's children, as the log under the body reads them.

    `total` is the level's own size rather than the page's: the heading counts the level, and
    the pager under it is cut from the same number.
    """

    shape: Shape
    rows: Sequence[Logged]
    total: int
    pager: Pager | None


class NodePage(NamedTuple):
    """One node of a session read whole: everything the page draws, and what it ran to get it.

    `selection` is the one value every part reads — it names the tab, heads the crumb chain and
    titles the body — so it stands apart from the four groups around it. `suffix` is what every
    href on the page carries, so a click serves the URL it displays.
    """

    selection: Node
    nav: Nav
    body: Body
    bearings: Bearings
    children: Children
    citations: Mapping[str, Cited]
    suffix: str


class Expansion(NamedTuple):
    """One child opened in place: its body, and the first page of whatever it holds.

    The same title, facts and details the pane draws, read from the same header queries, minus
    everything about where the node sits — an expansion arrives inside somebody else's log and
    stands as a row of it, which is what `span` is for.
    """

    node: Node
    facts: Facts
    shape: Shape
    # What the full view would have listed, counted, where the kind has a column to count it.
    children: int | None
    rows: Sequence[Logged]
    citations: Mapping[str, Cited]
    # How many columns of the log it opened under the expansion spans.
    span: int


class Popover(NamedTuple):
    """The numbers behind one NavTree row, for a node made of api calls.

    What the row already shows — the cost badge and the context bar — written out: the window
    the node ended on, the charges it ran up, and where the agent runs under it hang.
    """

    key: str
    citation: str
    window: Window
    charges: Sequence[Charge]
    total_wash: str
    # None where no agent run hangs under the node, which is what keeps the breakout off
    # every other row.
    breakout: Breakout | None


class Measured(NamedTuple):
    """One popover whose row is drawn as it was read: a tool call, or a compaction.

    Neither is made of api calls, so neither has a window to stand on or a dollar to wash —
    what each is measured in is its own, and the component for it is the reading's own type.
    """

    key: str
    citation: str
    node: Tool | Compaction


class Detailed(NamedTuple):
    """One fat value fetched whole, and how the block it comes back in marks it up.

    `syntax` is nothing for the two prose arms, which are marked up as what they are written
    in rather than as a language (`view/detail.py:syntax_of`).
    """

    whole: Whole
    syntax: highlight.Syntax | None
