"""A value too fat for the pane it lands in: the head it shows, and the way to the rest.

Nothing here decides how much to show — the head arrives already cut, in SQL, at the `?detail=`
the request asked for. What a `Detail` adds is what the pane needs beside the head: how much
was left behind, where to fetch it, and how to mark it up. The enrichment lines are the same
shape, because a pass writes past the width as readily as a transcript does; their specs are
declared beside the pass's other reads (`view/enrichment.py:LINES`).

`DETAILS` is where each of a node's values is declared, once: its name, the fetch that answers
it whole, the URL that fetch serves at, and how it was written. A pane reads a spec through
`preview` and the fetch reads the same spec, so the six places that used to agree by string
equality are one entry.
"""

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any, NamedTuple, assert_never

from hyphae.models.citation import Citation
from hyphae.models.node import WholeValue
from hyphae.store.handle import Store
from hyphae.store.pages import Value, page_rows
from hyphae.view import bounds
from hyphae.view.text import format as fmt
from hyphae.view.text import highlight


class Detail(NamedTuple):
    """One fat column of a node as its pane shows it: the head, and the way to the rest.

    A pane never decides how much of a value it shows — the head is cut in SQL at the
    `?detail=` the request asked for, and `cut` is what that left for the link to offer.
    """

    name: str
    head: str
    cut: int
    url: str
    # What the head is marked up as, where the record says what the value is written in — the
    # shell a `Bash` call ran, the file a `Read` returned.
    syntax: highlight.Syntax | None
    # And whether what is left is the markdown someone wrote it in. A person and a model write
    # markdown; a program writes what it writes, so a tool's arguments and its output are
    # printed as the store holds them. No value is both, and a syntax the record named wins.
    markdown: bool


class Written(StrEnum):
    """How a Detail was written, which decides how both surfaces render it."""

    # A person or a model wrote it, so it is prose and rendered as the markdown it was
    # written in. Every other member is something a program wrote, printed as it was stored.
    MARKDOWN = "markdown"
    # The two a record names outright: a `Bash` call ran shell, and a tool's arguments are an
    # object, so neither has to ask the row what it is holding.
    BASH = "bash"
    JSON = "json"
    # And the one that does ask: the suffix of the file a `Read` returned, else JSON. It is
    # the one arm whose fetch binds `head_chars`, because that suffix is cut in SQL.
    NAMED_FILE = "file"
    # A line an enrichment pass wrote: a span rather than a block, and the only kind whose
    # fetch is gated — a store no pass has touched holds no table to read it from.
    LINE = "line"


# What answers a Detail whole: the keys off its route in, the value with its citation out, and
# None where the store holds no row under those keys.
Fetch = Callable[[Store, Mapping[str, str]], WholeValue | None]


class Spec(NamedTuple):
    """One Detail, declared once: what a pane previews and what the fetch behind it serves."""

    # The label key, the pane's `data-detail`, and the column the header row previews the
    # head under — `f"{name}_chars"` beside it, holding the whole length the link offers.
    name: str
    # Where the whole of it is fetched from, as the route template FastAPI is given: the pane
    # mints its link by filling the same template with the keys of the node it is about.
    route: str
    # What serves it whole, keyed by what the route carries.
    whole: Fetch
    written: Written


def fetched(value: Value) -> Fetch:
    """One per-value statement as the `Fetch` a spec names, until a repository answers it.

    A repository PR replaces each use, and the PR that leaves no caller deletes this
    (`plans/store-layering/phase-4-repositories.md`).
    """

    def fetch(store: Store, keys: Mapping[str, str]) -> WholeValue | None:
        # The statement decides whether a width is bound: only the named-file read declares
        # `head_chars`, and it is not a cut of the answer — which rides whole — but the bound on
        # the file suffix beside it. A fetch prints at the pane's widths, so it names its surface.
        keyed = bounds.bound(value, bounds.HEADER_WIDTHS, **keys)
        rows = page_rows(store, value, **keyed)
        if not rows:
            return None
        return WholeValue(citation=Citation(value.value, keyed), **rows[0])

    return fetch


# What a turn's pane previews: what it was asked, and what followed the slash command it ran.
TURN_PROMPT = Spec(
    "prompt",
    "/fragment/prompt/session/{session_id}/thread/{source}/turn/{turn_id}",
    fetched(Value.TURN_PROMPT),
    Written.MARKDOWN,
)
TURN_COMMAND_ARGS = Spec(
    "command_args",
    "/fragment/args/session/{session_id}/thread/{source}/turn/{turn_id}",
    fetched(Value.TURN_COMMAND_ARGS),
    Written.MARKDOWN,
)
# What an agent run's pane previews: its brief, and the ask and the answer off the call that
# spawned it. All three markdown — one was written by whoever spawned the run, one by the run.
RUN_BRIEF = Spec(
    "brief",
    "/fragment/brief/session/{session_id}/run/{run_id}",
    fetched(Value.RUN_BRIEF),
    Written.MARKDOWN,
)
RUN_PROMPT = Spec(
    "prompt",
    "/fragment/prompt/session/{session_id}/run/{run_id}",
    fetched(Value.RUN_PROMPT),
    Written.MARKDOWN,
)
RUN_RESULT = Spec(
    "result",
    "/fragment/result/session/{session_id}/run/{run_id}",
    fetched(Value.RUN_RESULT),
    Written.MARKDOWN,
)
# What an api call's pane previews: what it said and what it thought, both the model's prose.
CALL_TEXT = Spec(
    "text",
    "/fragment/text/session/{session_id}/thread/{source}/call/{api_call_id}",
    fetched(Value.CALL_TEXT),
    Written.MARKDOWN,
)
CALL_THINKING = Spec(
    "thinking",
    "/fragment/thinking/session/{session_id}/thread/{source}/call/{api_call_id}",
    fetched(Value.CALL_THINKING),
    Written.MARKDOWN,
)
# And what a tool call's pane previews. The command first, where the call ran one: it is what
# the input is about, and the input below it is the record it was read out of.
TOOL_COMMAND = Spec(
    "command",
    "/fragment/command/session/{session_id}/thread/{source}/tool/{tool_call_id}",
    fetched(Value.TOOL_COMMAND),
    Written.BASH,
)
TOOL_INPUT = Spec(
    "input",
    "/fragment/input/session/{session_id}/thread/{source}/tool/{tool_call_id}",
    fetched(Value.TOOL_INPUT),
    Written.JSON,
)
TOOL_RESULT = Spec(
    "result",
    "/fragment/result/session/{session_id}/thread/{source}/tool/{tool_call_id}",
    fetched(Value.TOOL_RESULT),
    Written.NAMED_FILE,
)
# Every Detail of a node's own, and the only place one is declared; what a pass wrote about
# the node is declared beside the pass (`view/enrichment.py:LINES`), and the routes serve both.
# A route that answers a whole value and is in neither is not a Detail: nothing previews a
# head of it (`/fragment/record`, which arrives with a header line of its own).
DETAILS: tuple[Spec, ...] = (
    TURN_PROMPT,
    TURN_COMMAND_ARGS,
    RUN_BRIEF,
    RUN_PROMPT,
    RUN_RESULT,
    CALL_TEXT,
    CALL_THINKING,
    TOOL_COMMAND,
    TOOL_INPUT,
    TOOL_RESULT,
)


def syntax_of(written: Written, row: Mapping[str, Any]) -> highlight.Syntax | None:
    """What a value is marked up as, decided once for the preview and the fetch alike.

    None is prose: everything a session or a pass wrote is prose until something says
    otherwise. `NAMED_FILE` is the one arm that asks the row, and it asks by subscript — a
    query that stopped selecting `result_type` is a crash here rather than a value quietly
    marked up as the JSON a suffix-less file falls back to.
    """
    match written:
        case Written.MARKDOWN | Written.LINE:
            return None
        case Written.BASH:
            return highlight.Syntax.BASH
        case Written.JSON:
            return highlight.Syntax.JSON
        case Written.NAMED_FILE:
            return highlight.by_suffix(row["result_type"]) or highlight.Syntax.JSON
        case _:
            assert_never(written)


def preview(spec: Spec, row: Mapping[str, Any], *, size: int, **keys: str) -> Detail | None:
    """One spec's value as its pane shows it, or None where the store holds nothing under it.

    `row` is the header query's row, read under the spec's own name: the head one character
    past `size` — the cut-and-mark protocol `view/text/format.py:cut` reads — and the whole
    length beside it. Nothing is a NULL and an empty string alike: a value with no characters
    in it has no preview to show and nothing to offer the rest of.

    `keys` are the ids of the node the pane is about, which fill the spec's route template to
    mint the link. Passing one the template does not name is harmless; missing one is a
    `KeyError`, which is the URL that would otherwise have been minted wrong.
    """
    head = row[spec.name]
    if not head:
        return None
    # Read rather than defended: a length column is NULL only where the value beside it is,
    # which the line above already left. A header that answers one and not the other is a
    # query that stopped keeping the spec's bargain, and it crashes here.
    chars = row[f"{spec.name}_chars"]
    return Detail(
        name=spec.name,
        head=fmt.cut(head, size),
        cut=chars - size if len(head) > size else 0,
        url=spec.route.format(**keys),
        syntax=syntax_of(spec.written, row),
        markdown=spec.written is Written.MARKDOWN,
    )


def details(*maybe: Detail | None) -> list[Detail]:
    """The details a pane shows: whichever of the columns it asked for the store held."""
    return [item for item in maybe if item is not None]
