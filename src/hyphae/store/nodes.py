"""The node page's reads: a node's header and values, its children, its numbers, its record.

`NodeRepository` is the seam: the page and an expansion call `header` with the model of the
kind they read and the keys its statement binds, at the surface's widths and the sizes the
URL asked; a detail's fetch calls `value` with the header's model and the field the header
cut, and reads the whole of it back with the citation the fragment's footer quotes. A
children log pages through `children` and the two timelines, a NavTree row's popover reads
its numbers, and the pane joins a turn to its transcript line and reads one line whole.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from hyphae.models.citation import Citation, ParamValue
from hyphae.models.listing import Answer, Listed
from hyphae.models.node import (
    CallHeader,
    CallRow,
    CompactionNumbers,
    CompactionRow,
    NodeHeader,
    NodeNumbers,
    RunHeader,
    TimelineRow,
    ToolHeader,
    ToolNumbers,
    ToolRow,
    TurnHeader,
    TurnRecord,
    WholeValue,
)
from hyphae.models.record import WholeRecord
from hyphae.store import library, paging

if TYPE_CHECKING:
    # The handle hands out this repository, and this repository holds the handle: the one cycle
    # the design has, so the name is the checker's only.
    from hyphae.store.handle import Store

# The statement each header model is built from: one node read whole, the header of its own
# page. One per kind that has fields of its own; a bucket has none, and a compaction reads
# out of `view_compactions`.
HEADERS: dict[type[NodeHeader], str] = {
    TurnHeader: "view_turn_header",
    RunHeader: "view_run_header",
    CallHeader: "view_call_header",
    ToolHeader: "view_tool_header",
}

# The statement that answers one of a header's fat fields whole, by the header and the field
# it cut: the ten values a node's pane previews out of its header and fetches the rest of.
# A `Bash` call's command is a value of its own because a shell command is read as shell, not
# as a string inside JSON; a run's prompt and result are read off the call that spawned it.
VALUES: dict[tuple[type[NodeHeader], str], str] = {
    (TurnHeader, "prompt"): "view_turn_prompt",
    (TurnHeader, "command_args"): "view_turn_command_args",
    (RunHeader, "brief"): "view_run_brief",
    (RunHeader, "prompt"): "view_run_prompt",
    (RunHeader, "result"): "view_run_result",
    (CallHeader, "text"): "view_call_text",
    (CallHeader, "thinking"): "view_call_thinking",
    (ToolHeader, "input"): "view_tool_input",
    (ToolHeader, "result"): "view_tool_result",
    (ToolHeader, "command"): "view_tool_command",
}

# The statement that pages one shape of children log, by the row model it lists, and what
# that statement calls its page size: the api calls under a turn — or, at `turn_id` NULL,
# under a thread's bucket — and the tool calls under an api call. Each limits itself, so
# its rows carry the level's count and `paging.listed` reads it off them.
CHILDREN: dict[type[CallRow | ToolRow], tuple[str, str]] = {
    CallRow: ("view_turn_calls", "page_calls"),
    ToolRow: ("view_call_tools", "page_tools"),
}

# The two timelines, one per thread kind, shared with `hp query`: neither limits itself,
# because a report cites the rows whole, so a page is cut around them (`store/paging.py`).
TIMELINE = "session_timeline"
RUN_TIMELINE = "run_timeline"
COMPACTIONS = "view_compactions"
NUMBERS = "view_numbers"
TOOL_NUMBERS = "view_numbers_tool"
COMPACTION_NUMBERS = "view_numbers_compaction"
TURN_RECORDS = "view_turn_records"
RECORD = "view_record"


class NodeRepository:
    """The node page's reads, over one open store: `store.nodes`.

    The keys ride as one mapping because which keys a node has is the kind's business
    (`view/pages/node/kinds.py`), and the widths and sizes are keyword-only mappings
    (`bounds.HEADER_WIDTHS._asdict()`, the URL's `detail_chars`); `library.bind` fills what
    the statement declares and refuses the rest. A plain class rather than a dataclass:
    mutmut skips every decorated class, and the handle builds one of these per store anyway.
    """

    def __init__(self, store: "Store") -> None:
        self.store = store

    def header[H: NodeHeader](
        self,
        model: type[H],
        keys: Mapping[str, str],
        *,
        widths: Mapping[str, int],
        sizes: Mapping[str, int],
    ) -> H | None:
        """One node's header as its model, or None where the store holds no node at those keys."""
        statement = HEADERS[model]
        bindings = library.bind(statement, widths, sizes, **keys)
        row = library.one(self.store, statement, bindings)
        return None if row is None else model(citation=Citation(statement, bindings), **row)

    def value(
        self,
        model: type[NodeHeader],
        field: str,
        keys: Mapping[str, str],
        *,
        widths: Mapping[str, int],
    ) -> WholeValue | None:
        """The whole of one field the header cut, or None where the store holds no such node.

        A node the store holds with nothing under the field — a `Read` has no command, a turn
        no prompt — is a `WholeValue` whose `value` is None: the row, without the value.
        """
        statement = VALUES[model, field]
        bindings = library.bind(statement, widths, {}, **keys)
        row = library.one(self.store, statement, bindings)
        return None if row is None else WholeValue(citation=Citation(statement, bindings), **row)

    # --- the children logs ---------------------------------------------------------------

    def children[C: CallRow | ToolRow](
        self,
        model: type[C],
        keys: Mapping[str, ParamValue],
        *,
        skipped: int,
        size: int,
        widths: Mapping[str, int],
    ) -> Listed[C]:
        """One numbered page of the children a log lists under a node, with the level counted.

        `skipped` and `size` bind beside the keys rather than as sizes, because the statement
        pages itself and the footer quotes them where the keys are.
        """
        statement, page_size = CHILDREN[model]
        bindings = library.bind(statement, widths, {}, **keys, skipped=skipped, **{page_size: size})
        rows = library.fetch(self.store, library.load(statement), bindings)
        return paging.listed([model(**row) for row in rows], Citation(statement, bindings))

    def timeline(
        self, *, session_id: str, skipped: int, size: int, widths: Mapping[str, int]
    ) -> Listed[TimelineRow]:
        """One page of the main thread's turns, cut around the timeline a report cites."""
        bindings = library.bind(TIMELINE, widths, {}, session_id=session_id)
        return self._windowed(TIMELINE, bindings, skipped, size)

    def run_timeline(
        self, *, session_id: str, source: str, skipped: int, size: int, widths: Mapping[str, int]
    ) -> Listed[TimelineRow]:
        """One page of an agent run's own turns, keyed by the run id its rows carry as source."""
        bindings = library.bind(RUN_TIMELINE, widths, {}, session_id=session_id, source=source)
        return self._windowed(RUN_TIMELINE, bindings, skipped, size)

    def _windowed(
        self, statement: str, bindings: Mapping[str, ParamValue], skipped: int, size: int
    ) -> Listed[TimelineRow]:
        rows = paging.window(self.store, statement, paging.TURN_CURSOR, skipped, size, **bindings)
        # The offset and the limit after the statement's own bindings: what the page composed
        # around the query is as much a part of what produced it as a bound parameter.
        cited = Citation(statement, {**bindings, "offset": skipped, "limit": size})
        return paging.listed([TimelineRow(**row) for row in rows], cited)

    def compactions(
        self, *, session_id: str, source: str, widths: Mapping[str, int]
    ) -> Answer[CompactionRow]:
        """Every compaction of one thread, in order: what the NavTree marks and a compaction's
        own page is picked out of."""
        bindings = library.bind(COMPACTIONS, widths, {}, session_id=session_id, source=source)
        rows = library.fetch(self.store, library.load(COMPACTIONS), bindings)
        return Answer([CompactionRow(**row) for row in rows], Citation(COMPACTIONS, bindings))

    # --- the popovers --------------------------------------------------------------------

    def numbers(
        self,
        *,
        kind: str,
        session_id: str,
        source: str,
        node_id: str,
        widths: Mapping[str, int],
    ) -> NodeNumbers:
        """The numbers behind one NavTree row of a node made of api calls.

        `kind` names which api calls the node is, in the statement's words; `source` is the
        thread its window is read on. The statement aggregates, so a node the store never held
        answers as readily as one it did — a reading of nothing, never None.
        """
        bindings = library.bind(
            NUMBERS, widths, {}, session_id=session_id, source=source, node_id=node_id, kind=kind
        )
        (row,) = library.fetch(self.store, library.load(NUMBERS), bindings)
        return NodeNumbers(citation=Citation(NUMBERS, bindings), **row)

    def tool_numbers(
        self, *, session_id: str, source: str, tool_call_id: str, widths: Mapping[str, int]
    ) -> ToolNumbers | None:
        """The numbers behind one NavTree row of a tool call, or None where the store holds none."""
        bindings = library.bind(
            TOOL_NUMBERS,
            widths,
            {},
            session_id=session_id,
            source=source,
            tool_call_id=tool_call_id,
        )
        row = library.one(self.store, TOOL_NUMBERS, bindings)
        return (
            None if row is None else ToolNumbers(citation=Citation(TOOL_NUMBERS, bindings), **row)
        )

    def compaction_numbers(
        self, *, session_id: str, source: str, compaction_id: str, widths: Mapping[str, int]
    ) -> CompactionNumbers | None:
        """The numbers behind one NavTree row of a compaction; None where the store holds none."""
        bindings = library.bind(
            COMPACTION_NUMBERS,
            widths,
            {},
            session_id=session_id,
            source=source,
            compaction_id=compaction_id,
        )
        row = library.one(self.store, COMPACTION_NUMBERS, bindings)
        if row is None:
            return None
        return CompactionNumbers(citation=Citation(COMPACTION_NUMBERS, bindings), **row)

    # --- the records behind a thread -----------------------------------------------------

    def turn_records(self, *, session_id: str, source: str) -> Answer[TurnRecord]:
        """Which transcript line each turn of one thread was read from.

        Read for the whole thread because that is what the statement answers; the pane keeps
        the one row it is about.
        """
        bindings = library.bind(TURN_RECORDS, {}, {}, session_id=session_id, source=source)
        rows = library.fetch(self.store, library.load(TURN_RECORDS), bindings)
        return Answer([TurnRecord(**row) for row in rows], Citation(TURN_RECORDS, bindings))

    def record(self, *, session_id: str, source: str, line_no: int) -> WholeRecord | None:
        """One archived record whole, at the line the citation names, or None past the thread."""
        bindings = library.bind(
            RECORD, {}, {}, session_id=session_id, source=source, line_no=line_no
        )
        row = library.one(self.store, RECORD, bindings)
        return None if row is None else WholeRecord(citation=Citation(RECORD, bindings), **row)
