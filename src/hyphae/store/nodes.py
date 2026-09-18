"""The node page's reads: one node's header whole, and one of its fat values whole.

`NodeRepository` is the seam: the page and an expansion call `header` with the model of the
kind they read and the keys its statement binds, at the surface's widths and the sizes the
URL asked; a detail's fetch calls `value` with the header's model and the field the header
cut, and reads the whole of it back with the citation the fragment's footer quotes.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from hyphae.models.citation import Citation
from hyphae.models.node import (
    CallHeader,
    NodeHeader,
    RunHeader,
    ToolHeader,
    TurnHeader,
    WholeValue,
)
from hyphae.store import library

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
