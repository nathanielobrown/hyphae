"""One store row read into the shape the node page's markup takes: facts, a log row, numbers.

The seam the markup sits behind. A body and a log row read a `Row`, whatever columns the query
returned; a popover and a record read the model `store.nodes` built. Past here the markup reads
named fields of a type it declares itself, so a query that dropped a column raises here rather
than printing a dash under a label (`view/pages/node/markup/`).

The node itself is built one layer down (`view/builders.py`): what a row is *called* is the
same wherever it is read, and only what a row is *shown as* is this page's own.
"""

from typing import NamedTuple

from hyphae.models.node import CompactionNumbers, NodeNumbers, SpentGroup, ToolNumbers
from hyphae.models.record import WholeRecord
from hyphae.pricing import TokenUsage
from hyphae.store import library
from hyphae.store.pages import Row
from hyphae.view.builders import tool_about, tool_titles
from hyphae.view.nodes import Kind, Node
from hyphae.view.pages.node import models
from hyphae.view.pages.node.columns import Shape
from hyphae.view.pages.node.numbers import Numbers


def _read[F: NamedTuple](facts: type[F], row: Row) -> F:
    """One facts type filled from the columns its own fields name.

    The field names *are* the column names, which is what keeps a facts type and its header
    query in step: a query that dropped a column raises here, naming it, rather than reaching
    a body that would print a dash under its label.
    """
    return facts._make(row[field] for field in facts._fields)


def node_facts(node: Node, row: Row) -> models.Facts:
    """The facts a node's body prints, read off the row its header query answered.

    Where a store row stops being a bag of columns: past here a body reads named fields of a
    type. Total over `Kind`, the two buckets sharing a shape because neither is a row of the
    store — what they hold is counted on the node itself.
    """
    match node.kind:
        case Kind.SESSION:
            return _read(models.SessionFacts, row)
        case Kind.TURN:
            return _read(models.TurnFacts, row)
        case Kind.RUN:
            return _read(models.RunFacts, row)
        case Kind.CALL:
            return _read(models.CallFacts, row)
        case Kind.TOOL:
            return _read(models.ToolFacts, row)
        case Kind.COMPACTION:
            return _read(models.CompactionFacts, row)
        case Kind.UNATTRIBUTED | Kind.UNATTACHED:
            # The one kind not read off a row: a bucket stands for no store row, so its two
            # numbers are the ones the node already carries from counting its children.
            return models.BucketFacts(
                cost_usd=node.cost_usd, unpriced_api_calls=node.unpriced_api_calls
            )


def logged(shape: Shape, node: Node, row: Row) -> models.Logged:
    """One row of a children log: the node its wide column links to, beside what the row prints.

    Keyed by the log's shape rather than the node's kind, because the shape is what decides the
    columns the row has to fill. `Shape.NONE` lists nothing, so it has no row to build.
    """
    match shape:
        case Shape.TURNS:
            return models.LoggedTurn(
                node=node,
                turn_index=row["turn_index"],
                api_calls=row["api_calls"],
                tool_calls=row["tool_calls"],
                started_at=row["started_at"],
            )
        case Shape.CALLS:
            return models.LoggedCall(
                node=node,
                call_index=row["call_index"],
                model=row["model"],
                text=row["text"],
                tool_calls=row["tool_calls"],
                # The words rather than the rows: naming a tool call is Python's
                # (`view/text/tool_names.py`), so the query ships the fields and this composes them.
                called=", ".join(tool_titles(row.get("called_tools") or ())),
                text_chars=row["text_chars"],
                started_at=row["started_at"],
            )
        case Shape.TOOLS:
            return models.LoggedTool(
                node=node,
                tool_index=row["tool_index"],
                name=row["name"],
                about=tool_about(row.get("name") or "", row.get("fields")),
                is_error=row["is_error"],
                result_chars=row["result_chars"],
                started_at=row["started_at"],
            )
        case Shape.RUNS:
            return models.LoggedRun(
                node=node,
                agent_type=row["agent_type"],
                tool_errors=row["tool_errors"],
                started_at=row["started_at"],
            )
        case Shape.NONE:
            raise ValueError("A log of no shape lists no rows.")


def node_numbers(read: NodeNumbers) -> Numbers:
    """A popover's readings for a node made of api calls, off what `store.nodes.numbers` read.

    The whole reading at once — the window the component prints, the counts and dollars the
    charge lines are composed from, and the per-model groups they are priced at — so the
    route past here reads named fields rather than the store's model six more times.
    """
    return Numbers(
        window=models.Window(
            model=read.model,
            fill=read.fill,
            window_tokens=read.window_tokens,
            added=read.added,
            cost_usd=read.cost_usd,
            api_calls=read.api_calls,
            unpriced_api_calls=read.unpriced_api_calls,
        ),
        cache_read_tokens=read.cache_read_tokens,
        new_input_tokens=read.new_input_tokens,
        output_tokens=read.output_tokens,
        cost_usd=read.cost_usd,
        subtree_usd=read.subtree_usd,
        session_usd=read.session_usd,
        spent=tuple((group["model"], _usage(group)) for group in read.spent),
    )


def _usage(group: SpentGroup) -> TokenUsage:
    """One model's summed tokens as the price table takes them.

    The TTL split is summed per call in SQL, under the same fallback `pricing.py` applies to
    one — a call that reported no split puts its whole write on the 5-minute rate — so the
    group carries a split whether or not every call in it did.
    """
    return TokenUsage(
        input=group["input_tokens"],
        output=group["output_tokens"],
        cache_read=group["cache_read_tokens"],
        cache_creation=group["cache_creation_tokens"],
        cache_5m=group["cache_5m_tokens"],
        cache_1h=group["cache_1h_tokens"],
    )


def tool_numbers(read: ToolNumbers) -> models.Tool:
    """A popover's readings for one tool call, off what `store.nodes.tool_numbers` read.

    The siblings are named here rather than in the query: what a tool call is called is
    Python's (`view/text/tool_names.py`), and the query ships the fields each name is composed of.
    """
    return models.Tool(
        input_chars=read.input_chars,
        result_chars=read.result_chars,
        offload_file=read.offload_file,
        spawned_run=read.spawned_run,
        siblings=tool_titles(read.siblings),
        siblings_cut=read.siblings_cut,
    )


def compaction_numbers(read: CompactionNumbers) -> models.Compaction:
    """A popover's readings for one compaction, off what `store.nodes.compaction_numbers` read."""
    return models.Compaction(
        pre_tokens=read.pre_tokens,
        post_tokens=read.post_tokens,
        freed=read.freed,
        trigger=read.trigger,
    )


def record_value(whole: WholeRecord) -> models.Record:
    """One archived record as its fragment prints it, with its citation as the footer's line."""
    return models.Record(
        line_no=whole.line_no,
        type=whole.type,
        uuid=whole.uuid,
        timestamp=whole.timestamp,
        raw_chars=whole.raw_chars,
        raw=whole.raw,
        citation=library.citation(*whole.citation),
    )
