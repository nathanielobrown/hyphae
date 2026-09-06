"""The pane's children log: one numbered page of what is under a node, a row per child.

A table, because the row is a handful of numbers and a reader who cannot tell an api-call count
from a tool-call count from a time of day is reading nothing. The columns are the shape's own
and come from `view/columns.py:COLUMNS` — the head below writes them and every row fills all of
them, so a cell is always under its own heading. The words above them are the registry's, the
same one a pane's facts read.

A row is a line that gets a reader to the child's own page rather than a preview of it: what it
prints in the wide column is the child's title, the same words the NavTree row and the pane
heading use (`docs/viewer.md`).

The four row types below are what a route hands in instead of a store row: the shape decides
the columns, and the type of the row decides the cells, so a query that stopped returning a
column is a type error rather than a blank cell under a heading.
"""

from collections.abc import Sequence
from typing import assert_never

import htpy

from hyphae.view.components import Html, parts
from hyphae.view.models import Pager
from hyphae.view.nodes import Node
from hyphae.view.pages.node.columns import COLUMNS, Column, Shape, css
from hyphae.view.pages.node.markup.nav_tree import PANE_SWAP
from hyphae.view.pages.node.models import Logged, LoggedCall, LoggedRun, LoggedTool, LoggedTurn
from hyphae.view.text import cuts
from hyphae.view.text import format as fmt
from hyphae.view.text.labels import label

# Spread per row rather than hoisted onto the table, because the button in the last column is an
# `hx-get` of its own that must not swap the pane: a hoisted attribute would have to be undone on
# it, which is a line per row either way.

# And what the View button does instead: fetch the child's body and stand it under this row.
# The second swap vocabulary, named for the same reason as the first — an attribute spelt in
# two places is two answers to one question (`tests/view/test_components.py`).
OPEN_SWAP = {
    # Once: a second fetch would stand a second copy of the same body under the row.
    "hx-trigger": "click once",
    "hx-target": "closest tr",
    "hx-swap": "afterend",
}


def log(
    *,
    shape: Shape,
    rows: Sequence[Logged],
    total: int | None,
    suffix: str,
    pager: Pager | None,
    opens: bool,
) -> Html | None:
    """One page of a node's children, or nothing where the node has no level under it.

    The heading counts the level and not the page: a reader who lands on page 2 of a turn's
    calls is reading a turn of however many calls it made, not a turn of a hundred.

    `opens` is whether a row here can be opened in place. False inside an expansion, which is
    already one level opened: the rows carry no button and the table drops the column that
    holds one, because an expansion inside an expansion is the accordion of accordions the pane
    is built to avoid (`.claude/rules/viewer-ui.md`).
    """
    if shape is Shape.NONE:
        return None
    return htpy.section(".log", data_log=shape)[
        [
            htpy.h2[[htpy.span(data_field="children")[fmt.count(total)], f" {shape}"]],
            htpy.table[
                [
                    htpy.thead[
                        htpy.tr(data_columns=shape)[
                            [
                                _head(column=column)
                                for column in COLUMNS[shape]
                                if opens or column.field != "body"
                            ]
                        ]
                    ],
                    htpy.tbody[
                        [_row(shape=shape, row=row, suffix=suffix, opens=opens) for row in rows],
                    ],
                ]
            ],
            # Only where the level runs past one page: a control offering no page to go to
            # is one a reader has to read to learn there is nothing under it.
            parts.pager(name=shape, pages=pager) if pager else None,
        ]
    ]


def _head(*, column: Column) -> Html:
    """One column head: the mark, the space after it, and the word the registry gives the field."""
    return htpy.th(scope="col", data_column=column.field, class_=column.css or None)[
        [parts.mark(character=column.icon), " ", label(column.field)]
    ]


def _what(*, shape: Shape, node: Node, suffix: str, field: str, words: str, second: str) -> Html:
    """The one wide column of a row: what the child is called, linking to the child's own page.

    `second` is the line under it, in lower hierarchy — what the first line left out, which
    today is what a tool call was for where its title already says what it did
    (`view/builders.py:tool_about`). Empty on every other shape, which has one line to give.
    """
    url = f"{node.url}{suffix}"
    return htpy.td(data_column=field, class_=css(shape, field) or None)[
        [
            htpy.a(".primary", {"hx-get": url, **PANE_SWAP}, href=url)[
                [parts.glyph(enriched=node.enriched), htpy.span(data_field=field)[words]]
            ],
            htpy.span(".secondary", data_field="about")[second] if second else None,
        ]
    ]


def _row(*, shape: Shape, row: Logged, suffix: str, opens: bool) -> Html:
    """One child's row: the shape's own cells, the time it started, and the way to open it."""
    return htpy.tr(data_child=row.node.key)[
        [
            _cells(shape=shape, row=row, suffix=suffix),
            _cell(shape=shape, field="started_at", value=fmt.clock(row.started_at)),
            _opener(node=row.node, suffix=suffix) if opens else None,
        ]
    ]


def _cells(*, shape: Shape, row: Logged, suffix: str) -> Html:
    """The cells the row's own shape prints, in the order its columns head them.

    Total over the four kinds of row a log lists: a shape with no arm would print a row of the
    time it started and nothing else, under headings for the columns it dropped.
    """
    match row:
        case LoggedTurn():
            return htpy.fragment[
                [
                    _cell(shape=shape, field="turn_index", value=fmt.count(row.turn_index)),
                    _what(
                        shape=shape,
                        node=row.node,
                        suffix=suffix,
                        field="title",
                        words=row.node.log_title,
                        second="",
                    ),
                    _cell(shape=shape, field="api_calls", value=fmt.count(row.api_calls)),
                    _cell(shape=shape, field="tool_calls", value=fmt.count(row.tool_calls)),
                    _cell(shape=shape, field="cost_usd", value=fmt.money(row.node.cost_usd)),
                ]
            ]
        case LoggedCall():
            return htpy.fragment[
                [
                    _cell(shape=shape, field="call_index", value=fmt.count(row.call_index)),
                    _what(
                        shape=shape,
                        node=row.node,
                        suffix=suffix,
                        field="model",
                        words=cuts.line(row.model),
                        second="",
                    ),
                    _cell(shape=shape, field="text", value=cuts.line(row.text)),
                    _cell(shape=shape, field="tool_calls", value=fmt.count(row.tool_calls)),
                    _cell(shape=shape, field="tool_titles", value=cuts.line(row.called)),
                    _cell(shape=shape, field="text_chars", value=fmt.count(row.text_chars)),
                    _cell(shape=shape, field="cost_usd", value=fmt.money(row.node.cost_usd)),
                ]
            ]
        case LoggedTool():
            return htpy.fragment[
                [
                    _cell(shape=shape, field="tool_index", value=fmt.count(row.tool_index)),
                    _cell(shape=shape, field="name", value=cuts.line(row.name)),
                    # The title alone, with the name already in its own column beside it. What
                    # the call was for reads through the same cut, and is left out rather than
                    # dashed where the record says nothing: a dash under a command is a line of
                    # nothing where the second line means "and this is what it was for".
                    _what(
                        shape=shape,
                        node=row.node,
                        suffix=suffix,
                        field="title",
                        words=row.node.log_title,
                        second=cuts.line(row.about) if row.about else "",
                    ),
                    _cell(
                        shape=shape,
                        field="is_error",
                        value=fmt.text("error" if row.is_error else None),
                    ),
                    _cell(shape=shape, field="result_chars", value=fmt.count(row.result_chars)),
                ]
            ]
        case LoggedRun():
            return htpy.fragment[
                [
                    _cell(shape=shape, field="agent_type", value=cuts.line(row.agent_type)),
                    _what(
                        shape=shape,
                        node=row.node,
                        suffix=suffix,
                        field="title",
                        words=row.node.log_title,
                        second="",
                    ),
                    _cell(shape=shape, field="tool_errors", value=fmt.count(row.tool_errors)),
                    _cell(shape=shape, field="cost_usd", value=fmt.money(row.node.cost_usd)),
                ]
            ]
        case _:
            assert_never(row)


def _cell(*, shape: Shape, field: str, value: str) -> Html:
    """One cell of a row: the value under its own column, labelled for a test to read."""
    return htpy.td(data_column=field, class_=css(shape, field) or None)[
        htpy.span(data_field=field)[value]
    ]


def _opener(*, node: Node, suffix: str) -> Html:
    """The child's body, opened in place: one body, two mounts.

    It arrives on click, one request, and stops one level down: an api call's body lists the
    tools it called, as rows of this same table with no `View` of their own, and every other
    kind stands a count and a link to its own page. A button rather than a disclosure triangle,
    because a reader has to be able to see that a row opens.
    """
    return htpy.td(data_column="body")[
        htpy.button(
            ".button",
            {"hx-get": f"{node.expansion}{suffix}", **OPEN_SWAP},
            type="button",
            data_view=node.key,
        )["View"]
    ]
